"""Cross-validated component selection and per-component R2 / Q2.

For both PCA and PLS, fitting a model means choosing how many components to keep.
This module reports, per component count:

- ``r2`` - the in-sample (calibration) cumulative fraction of variance explained,
- ``q2`` - the cross-validated (out-of-sample) cumulative fraction predicted.

For PCA the target is the X block; for PLS it is the Y block. The recommended
number of components follows the library's selector, which offers several
selection rules (see :data:`SelectionRule`): the one-standard-error rule
(``"1se"``, the PLS default), the lowest cross-validated error (``"min"``, the
PCA default), a cumulative-Q2 increment threshold (``"q2_increment"``), or - for
PLS only - Van der Voet's randomization test (``"randomization"``). PCA also
chooses a cross-validation scheme (see :data:`CvScheme`): element-wise k-fold
(``"ekf"``, the default; Bro et al. 2008) or the legacy ``"row_wise"`` scheme.

The cross-validation itself - fold splitting, in-fold scaling, PRESS, the
validated R2, and the recommendation - is delegated to ``process_improve``'s
``PCA.select_n_components`` / ``PLS.select_n_components`` rather than
reimplemented here; we only adapt their output into one small,
serialization-friendly result. Both selectors report the cross-validated R2 (Q2)
directly - PCA via its ``q2`` field, PLS via the ``"total"`` column of
``r2y_validated`` - normalised the same way as the calibration R2, so R2 and Q2
are directly comparable.

Alongside the curves we report a per-component Q2 standard error (the half-width
of a +/-1 SE band around the Q2 line, for visualising the uncertainty behind the
1-SE rule) and, for PLS, how stable the recommendation was across cross-validation
repeats (whether the modal choice cleared the stability threshold, and its vote
share). The standard error is taken straight from the selector's ``q2_se`` field
(``process_improve`` >= 1.39); ScorePilot no longer derives it locally.

The selectors re-fit the centring/scaling inside each training fold
(``scale_inside_folds=True``), so passing the already-centered/scaled output of
:func:`apply_spec` is harmless (re-scaling already-scaled data is close to a
no-op) and the reported errors no longer leak the full-dataset scaling into the
held-out rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from process_improve.multivariate import PCA, PLS
from process_improve.multivariate.methods import NotEnoughVarianceError

from scorepilot.core.modeling import ModelKind

# A small, fixed fold count keeps cross-validation cheap (diagnostics recompute it
# on demand) and a fixed shuffle seed keeps the result deterministic across runs.
DEFAULT_N_SPLITS = 7
_RANDOM_STATE = 0

# How the recommended component count is chosen, and (PCA only) which
# cross-validation scheme produces the PRESS. These mirror the string options of
# ``process_improve``'s selectors; the values are passed straight through and
# validated there.
SelectionRule = Literal["1se", "min", "q2_increment", "randomization"]
CvScheme = Literal["ekf", "row_wise"]

# Rules each model kind supports (PCA has no randomization test) and their
# per-kind defaults, matching ``process_improve``'s own defaults.
PLS_RULES: tuple[SelectionRule, ...] = ("1se", "min", "q2_increment", "randomization")
PCA_RULES: tuple[SelectionRule, ...] = ("min", "1se", "q2_increment")
_DEFAULT_RULE: dict[ModelKind, SelectionRule] = {"PLS": "1se", "PCA": "min"}
# Repeated K-fold is the research-backed default for PLS's 1-SE rule; PCA's
# element-wise scheme already covers every cell once per repeat.
_DEFAULT_N_REPEATS: dict[ModelKind, int] = {"PLS": 10, "PCA": 1}
_DEFAULT_CV_SCHEME: CvScheme = "ekf"
# Marginal-Q2 threshold for the "q2_increment" rule; mirrors process_improve's
# own default (one percentage point of predicted variance).
_DEFAULT_MIN_Q2_INCREASE = 0.01


@dataclass(frozen=True)
class CrossValidation:
    """Per-component calibration R2 and cross-validated Q2 for a model."""

    kind: ModelKind
    target: str  # "X" for PCA, "Y" for PLS - what R2/Q2 describe.
    n_splits: int
    n_repeats: int
    selection_rule: SelectionRule  # how ``recommended`` was chosen
    cv_scheme: CvScheme | None  # PCA cross-validation scheme; None for PLS
    component_numbers: list[int]  # 1, 2, ..., A
    r2: list[float]  # cumulative calibration R2 after each component
    q2: list[float]  # cumulative cross-validated R2 (Q2) after each component
    # Standard error of Q2 per component (the half-width of a +/-1 SE band around
    # the Q2 curve), reported directly by the selector's ``q2_se`` field.
    q2_se: list[float]
    r2_per_component: list[float]
    q2_per_component: list[float]
    recommended: int  # component count recommended by the library's selector
    # Whether the PLS recommendation was stable across CV repeats (the modal
    # vote share cleared the selector's stability threshold). ``None`` when not
    # applicable (PCA, or a rule that does not vote across repeats).
    recommended_is_stable: bool | None
    # Fraction of CV repeats that voted for ``recommended`` (PLS only; the modal
    # vote share). ``None`` for PCA or rules that do not vote across repeats.
    recommended_vote_share: float | None


@dataclass(frozen=True)
class _Curves:
    """Internal: the per-kind selector output adapted into common arrays."""

    r2: list[float]
    q2: list[float]
    q2_se: list[float]
    recommended: int
    stable: bool | None
    vote_share: float | None


def _q2_se_list(q2_se: pd.Series, n: int) -> list[float]:
    """Adapt the selector's per-component Q2 standard error to a clean float list.

    ``process_improve`` >= 1.39 reports ``q2_se`` directly (the half-width of a
    +/-1 SE band around the validated Q2 curve), so ScorePilot just forwards it.
    Non-finite entries (a degenerate null sum-of-squares) collapse to 0.0.
    """
    values = np.asarray(q2_se.to_numpy(), dtype=float)[:n]
    return [float(v) if np.isfinite(v) else 0.0 for v in values]


def _cumulative_diffs(cumulative: list[float]) -> list[float]:
    return [cumulative[i] - (cumulative[i - 1] if i else 0.0) for i in range(len(cumulative))]


def cross_validate(
    x_block: pd.DataFrame,
    y_block: pd.DataFrame | None,
    kind: ModelKind,
    *,
    max_components: int | None = None,
    n_splits: int = DEFAULT_N_SPLITS,
    selection_rule: SelectionRule | None = None,
    cv_scheme: CvScheme | None = None,
    n_repeats: int | None = None,
    min_q2_increase: float | None = None,
) -> CrossValidation:
    """Evaluate a model at 1..A components and report R2, Q2, and a recommendation.

    Parameters
    ----------
    x_block, y_block
        Already preprocessed blocks from :func:`apply_spec`. ``y_block`` is
        required for PLS.
    max_components
        Largest component count to evaluate. Defaults to the data's rank.
    n_splits
        Number of K-fold splits (clamped to the number of observations). For PCA
        under the element-wise scheme this is the number of element folds.
    selection_rule
        Which rule chooses the recommended component count (see
        :data:`SelectionRule`). Defaults to ``"1se"`` for PLS and ``"min"`` for
        PCA. ``"randomization"`` is PLS-only.
    cv_scheme
        PCA cross-validation scheme (see :data:`CvScheme`); ignored for PLS.
        Defaults to ``"ekf"``.
    n_repeats
        How many times to repeat the (shuffled) cross-validation. Defaults to
        10 for PLS (the 1-SE rule needs the repeats) and 1 for PCA.
    min_q2_increase
        Threshold for the ``"q2_increment"`` rule; ignored by other rules.
        Defaults to the library's value.

    Raises
    ------
    ValueError
        For an unknown ``kind``, a PLS request without Y columns, an unsupported
        ``selection_rule`` for the kind, or data the underlying selector cannot
        cross-validate (including rank-deficient / collinear folds).
    """
    if kind not in ("PCA", "PLS"):
        msg = f"Unknown model kind: {kind!r} (expected 'PCA' or 'PLS')"
        raise ValueError(msg)
    n_rows = x_block.shape[0]
    if n_rows < 2:
        msg = "Cross-validation needs at least two observations."
        raise ValueError(msg)

    rule = selection_rule or _DEFAULT_RULE[kind]
    allowed = PLS_RULES if kind == "PLS" else PCA_RULES
    if rule not in allowed:
        choices = ", ".join(allowed)
        msg = f"selection_rule {rule!r} is not supported for {kind}; choose one of {choices}."
        raise ValueError(msg)
    repeats = n_repeats if n_repeats is not None else _DEFAULT_N_REPEATS[kind]
    increment = min_q2_increase if min_q2_increase is not None else _DEFAULT_MIN_Q2_INCREASE
    n_folds = max(2, min(n_splits, n_rows))
    scheme: CvScheme | None = None

    try:
        if kind == "PLS":
            if y_block is None or y_block.shape[1] == 0:
                msg = "PLS cross-validation requires at least one Y column."
                raise ValueError(msg)
            curves = _pls_curves(
                x_block,
                y_block,
                max_components,
                n_folds,
                selection_rule=rule,
                n_repeats=repeats,
                min_q2_increase=increment,
            )
            target = "Y"
        else:
            scheme = cv_scheme or _DEFAULT_CV_SCHEME
            curves = _pca_curves(
                x_block,
                max_components,
                n_folds,
                selection_rule=rule,
                cv_scheme=scheme,
                n_repeats=repeats,
                min_q2_increase=increment,
            )
            target = "X"
    except NotEnoughVarianceError as exc:  # more components than the data's rank supports
        msg = f"Too many components for the data available to cross-validate: {exc}"
        raise ValueError(msg) from exc
    except (RuntimeError, FloatingPointError, np.linalg.LinAlgError) as exc:
        # The selector could not converge - e.g. collinear / rank-deficient folds
        # make the PLS weight inversion ill-conditioned. Surface it as a clean
        # input error rather than letting it escape as a 500.
        raise ValueError(str(exc)) from exc

    return CrossValidation(
        kind=kind,
        target=target,
        n_splits=n_folds,
        n_repeats=repeats,
        selection_rule=rule,
        cv_scheme=scheme,
        component_numbers=list(range(1, len(curves.r2) + 1)),
        r2=curves.r2,
        q2=curves.q2,
        q2_se=curves.q2_se,
        r2_per_component=_cumulative_diffs(curves.r2),
        q2_per_component=_cumulative_diffs(curves.q2),
        recommended=curves.recommended,
        recommended_is_stable=curves.stable,
        recommended_vote_share=curves.vote_share,
    )


def _pca_curves(
    x_block: pd.DataFrame,
    max_components: int | None,
    n_folds: int,
    *,
    selection_rule: SelectionRule,
    cv_scheme: CvScheme,
    n_repeats: int,
    min_q2_increase: float,
) -> _Curves:
    """R2X, Q2X, the Q2 standard error, and recommendation for PCA.

    The selector reports the cross-validated R2X (Q2) per component directly in
    its ``q2`` field - PRESS normalised by the same null-model sum-of-squares the
    calibration ``r2_cumulative_`` uses - so R2 and Q2 are directly comparable.
    Under the element-wise scheme ``q2`` may legitimately go negative (a
    component predicting held-out cells worse than their column mean); ``q2`` is
    rejected only when it is non-finite, which means the block had no variance to
    cross-validate. The +/-1 SE band is the selector's ``q2_se``. PCA does not
    vote across repeats, so there is no stability or vote share to report.
    """
    selection = PCA.select_n_components(
        x_block,
        max_components=max_components,
        cv=n_folds,
        cv_scheme=cv_scheme,
        n_repeats=n_repeats,
        selection_rule=selection_rule,
        min_q2_increase=min_q2_increase,
        random_state=_RANDOM_STATE,
    )
    q2_values = np.asarray(selection.q2.to_numpy(), dtype=float)
    if not np.all(np.isfinite(q2_values)):
        msg = "The X block has no variance to cross-validate."
        raise ValueError(msg)
    q2 = [float(v) for v in q2_values]
    a_max = len(q2)
    r2 = [float(v) for v in np.asarray(PCA(n_components=a_max).fit(x_block).r2_cumulative_)[:a_max]]
    return _Curves(
        r2=r2,
        q2=q2,
        q2_se=_q2_se_list(selection.q2_se, a_max),
        recommended=int(selection.n_components),
        stable=None,
        vote_share=None,
    )


def _pls_curves(
    x_block: pd.DataFrame,
    y_block: pd.DataFrame,
    max_components: int | None,
    n_folds: int,
    *,
    selection_rule: SelectionRule,
    n_repeats: int,
    min_q2_increase: float,
) -> _Curves:
    """R2Y, Q2Y, the Q2 standard error, recommendation, and stability for PLS.

    The selector returns the validated R2Y per component directly (the ``"total"``
    column of ``r2y_validated``); the calibration R2Y is the fitted model's
    ``r2_cumulative_``. ``selection_is_stable`` reports whether the recommended
    count was the stable modal choice across the cross-validation repeats, and
    ``selection_distribution`` gives the per-count vote share. The +/-1 SE band is
    the selector's ``q2_se`` (the per-fold total-PRESS standard error on the Q2
    scale).
    """
    selection = PLS.select_n_components(
        x_block,
        y_block,
        max_components=max_components,
        cv=n_folds,
        n_repeats=n_repeats,
        selection_rule=selection_rule,
        min_q2_increase=min_q2_increase,
        random_state=_RANDOM_STATE,
    )
    q2 = [float(v) for v in selection.r2y_validated["total"].to_numpy()]
    a_max = len(q2)
    model = PLS(n_components=a_max, scale=False).fit(x_block, y_block)
    r2 = [float(v) for v in np.asarray(model.r2_cumulative_)[:a_max]]

    recommended = int(selection.n_components)
    stable = selection.selection_is_stable
    dist = selection.selection_distribution
    vote_share = (
        float(dist[recommended]) if dist is not None and recommended in dist.index else None
    )
    return _Curves(
        r2=r2,
        q2=q2,
        q2_se=_q2_se_list(selection.q2_se, a_max),
        recommended=recommended,
        stable=None if stable is None else bool(stable),
        vote_share=vote_share,
    )
