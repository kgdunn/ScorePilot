"""Cross-validated component selection and per-component R2 / Q2.

For both PCA and PLS, fitting a model means choosing how many components to keep.
This module reports, per component count:

- ``r2`` - the in-sample (calibration) cumulative fraction of variance explained,
- ``q2`` - the cross-validated (out-of-sample) cumulative fraction predicted.

For PCA the target is the X block; for PLS it is the Y block. The recommended
number of components follows the library's selector (Wold's PRESS-ratio criterion
for PCA, minimum RMSECV for PLS).

The cross-validation itself - fold splitting, PRESS, and the validated R2 - is
delegated to ``process_improve``'s ``PCA.select_n_components`` /
``PLS.select_n_components`` rather than reimplemented here; we only adapt their
output into one small, serialization-friendly result and (for PCA, whose selector
exposes PRESS but not a validated R2 directly) normalise PRESS by the same total
sum-of-squares the calibration R2 uses, so R2 and Q2 are directly comparable.

Like those selectors, this expects ``x_block`` (and ``y_block`` for PLS) to be the
already-centered/scaled output of :func:`apply_spec`, and refits on each fold
without re-deriving the scaling inside the fold; folds therefore share the scaling
of the full dataset, which makes the reported errors slightly optimistic.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from process_improve.multivariate import PCA, PLS
from sklearn.model_selection import KFold

from scorepilot.core.modeling import ModelKind

# A small, fixed fold count keeps cross-validation cheap (diagnostics recompute it
# on demand) and a fixed shuffle seed keeps the result deterministic across runs.
DEFAULT_N_SPLITS = 7
_RANDOM_STATE = 0


@dataclass(frozen=True)
class CrossValidation:
    """Per-component calibration R2 and cross-validated Q2 for a model."""

    kind: ModelKind
    target: str  # "X" for PCA, "Y" for PLS - what R2/Q2 describe.
    n_splits: int
    component_numbers: list[int]  # 1, 2, ..., A
    r2: list[float]  # cumulative calibration R2 after each component
    q2: list[float]  # cumulative cross-validated R2 (Q2) after each component
    r2_per_component: list[float]
    q2_per_component: list[float]
    recommended: int  # component count recommended by the library's selector


def _cumulative_diffs(cumulative: list[float]) -> list[float]:
    return [cumulative[i] - (cumulative[i - 1] if i else 0.0) for i in range(len(cumulative))]


def cross_validate(
    x_block: pd.DataFrame,
    y_block: pd.DataFrame | None,
    kind: ModelKind,
    *,
    max_components: int | None = None,
    n_splits: int = DEFAULT_N_SPLITS,
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
        Number of K-fold splits (clamped to the number of observations).

    Raises
    ------
    ValueError
        For an unknown ``kind``, a PLS request without Y columns, or data the
        underlying selector cannot cross-validate.
    """
    if kind not in ("PCA", "PLS"):
        msg = f"Unknown model kind: {kind!r} (expected 'PCA' or 'PLS')"
        raise ValueError(msg)
    n_rows = x_block.shape[0]
    if n_rows < 2:
        msg = "Cross-validation needs at least two observations."
        raise ValueError(msg)
    folds = KFold(n_splits=max(2, min(n_splits, n_rows)), shuffle=True, random_state=_RANDOM_STATE)

    try:
        if kind == "PLS":
            if y_block is None or y_block.shape[1] == 0:
                msg = "PLS cross-validation requires at least one Y column."
                raise ValueError(msg)
            r2, q2, recommended = _pls_curves(x_block, y_block, max_components, folds)
            target = "Y"
        else:
            r2, q2, recommended = _pca_curves(x_block, max_components, folds)
            target = "X"
    except (RuntimeError, FloatingPointError) as exc:  # selector could not converge
        raise ValueError(str(exc)) from exc

    return CrossValidation(
        kind=kind,
        target=target,
        n_splits=folds.get_n_splits(),
        component_numbers=list(range(1, len(r2) + 1)),
        r2=r2,
        q2=q2,
        r2_per_component=_cumulative_diffs(r2),
        q2_per_component=_cumulative_diffs(q2),
        recommended=recommended,
    )


def _pca_curves(
    x_block: pd.DataFrame, max_components: int | None, folds: KFold
) -> tuple[list[float], list[float], int]:
    """R2X, Q2X, and recommendation for PCA via ``PCA.select_n_components``.

    The selector exposes PRESS (mean squared cross-validated reconstruction error
    per cell) but not a validated R2. Dividing PRESS by the null-model error -
    the mean squared value of the centered block - yields ``Q2 = 1 - PRESS / SS``,
    the same normalisation the calibration ``r2_cumulative_`` uses, so the two
    curves are directly comparable.
    """
    selection = PCA.select_n_components(x_block, max_components=max_components, cv=folds)  # type: ignore[arg-type]
    press = np.asarray(selection.press.to_numpy(), dtype=float)
    a_max = len(press)
    baseline = float(np.nanmean(np.asarray(x_block.to_numpy(), dtype=float) ** 2))
    if baseline <= 0:
        msg = "The X block has no variance to cross-validate."
        raise ValueError(msg)
    q2 = [float(1.0 - p / baseline) for p in press]
    r2 = [float(v) for v in np.asarray(PCA(n_components=a_max).fit(x_block).r2_cumulative_)[:a_max]]
    return r2, q2, int(selection.n_components)


def _pls_curves(
    x_block: pd.DataFrame, y_block: pd.DataFrame, max_components: int | None, folds: KFold
) -> tuple[list[float], list[float], int]:
    """R2Y, Q2Y, and recommendation for PLS via ``PLS.select_n_components``.

    The selector returns the validated R2Y per component directly (the ``"total"``
    column of ``r2y_validated``); the calibration R2Y is the fitted model's
    ``r2_cumulative_``.
    """
    selection = PLS.select_n_components(x_block, y_block, max_components=max_components, cv=folds)  # type: ignore[arg-type]
    q2 = [float(v) for v in selection.r2y_validated["total"].to_numpy()]
    a_max = len(q2)
    model = PLS(n_components=a_max, scale=False).fit(x_block, y_block)
    r2 = [float(v) for v in np.asarray(model.r2_cumulative_)[:a_max]]
    return r2, q2, int(selection.n_components)
