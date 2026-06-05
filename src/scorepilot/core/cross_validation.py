"""Cross-validated component selection and per-component R2 / Q2.

For both PCA and PLS, fitting a model means choosing how many components to keep.
This module evaluates a model at 1, 2, ..., A components with K-fold
cross-validation and reports, per component count:

- ``r2`` - the in-sample (calibration) cumulative fraction of variance explained,
- ``q2`` - the cross-validated (out-of-sample) cumulative fraction predicted.

For PCA the target reconstructed is the X block; for PLS it is the Y block. The
recommended number of components is the count that maximises Q2 - i.e. the model
with the best predictive ability, "fit until the cross-validation number of
components" rather than however many the user happened to type.

Like ``process_improve``'s own selectors, this expects ``x_block`` (and ``y_block``
for PLS) to be the already-centered/scaled output of :func:`apply_spec`, and refits
on each fold without re-deriving the scaling inside the fold. Folds therefore share
the scaling of the full dataset, which makes the reported errors slightly
optimistic compared with scaling each training fold independently.
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
# How close to the best Q2 a smaller model may be before we prefer it: the
# recommended count is the fewest components within this tolerance of the peak,
# so a negligible later gain does not pull in an extra component.
_Q2_TOLERANCE = 0.01


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
    recommended: int  # component count maximising Q2 (at least 1)


def _weights_and_loadings(
    x_train: pd.DataFrame,
    y_train: pd.DataFrame | None,
    kind: ModelKind,
    n_components: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit a model and return ``(W, L)`` such that scores ``T = X @ W`` and the
    target is reconstructed as ``T[:, :a] @ L[:, :a].T``.

    For PCA the target is X and ``W = L`` are the orthonormal loadings. For PLS the
    target is Y, ``W`` are the direct (rotated) weights and ``L`` the Y-loadings.
    """
    if kind == "PLS":
        if y_train is None:
            msg = "PLS cross-validation requires a Y block."
            raise ValueError(msg)
        model = PLS(n_components=n_components, scale=False).fit(x_train, y_train)
        return (
            np.asarray(model.direct_weights_, dtype=float),
            np.asarray(model.y_loadings_, dtype=float),
        )
    model = PCA(n_components=n_components).fit(x_train)
    loadings = np.asarray(model.loadings_, dtype=float)
    return loadings, loadings


def _press_curve(
    weights: np.ndarray,
    loadings: np.ndarray,
    x_eval: np.ndarray,
    target_eval: np.ndarray,
    n_components: int,
) -> np.ndarray:
    """Squared reconstruction error of ``target_eval`` using 1..A components."""
    scores = x_eval @ weights
    press = np.empty(n_components)
    for a in range(1, n_components + 1):
        reconstructed = scores[:, :a] @ loadings[:, :a].T
        press[a - 1] = float(np.nansum((target_eval - reconstructed) ** 2))
    return press


def cross_validate(
    x_block: pd.DataFrame,
    y_block: pd.DataFrame | None,
    kind: ModelKind,
    *,
    max_components: int | None = None,
    n_splits: int = DEFAULT_N_SPLITS,
) -> CrossValidation:
    """Evaluate a model at 1..A components and pick the Q2-optimal count.

    Parameters
    ----------
    x_block, y_block
        Already preprocessed blocks from :func:`apply_spec`. ``y_block`` is
        required for PLS.
    max_components
        Largest component count to evaluate. Defaults to the data's rank
        (``min(n_observations - 1, n_variables)``).
    n_splits
        Number of K-fold splits (clamped to the number of observations).

    Raises
    ------
    ValueError
        For an unknown ``kind``, a PLS request without Y columns, or data too
        small to cross-validate (fewer than two usable folds).
    """
    if kind not in ("PCA", "PLS"):
        msg = f"Unknown model kind: {kind!r} (expected 'PCA' or 'PLS')"
        raise ValueError(msg)
    x = np.asarray(x_block.to_numpy(), dtype=float)
    n_rows, n_cols = x.shape

    if kind == "PLS":
        if y_block is None or y_block.shape[1] == 0:
            msg = "PLS cross-validation requires at least one Y column."
            raise ValueError(msg)
        target = np.asarray(y_block.to_numpy(), dtype=float)
    else:
        target = x

    n_splits = max(2, min(n_splits, n_rows))
    if n_rows < 2 or n_splits < 2:
        msg = "Cross-validation needs at least two observations."
        raise ValueError(msg)

    # Each fold must leave enough training rows to fit the largest model.
    min_train = n_rows - int(np.ceil(n_rows / n_splits))
    upper = min(min_train, n_cols)
    if upper < 1:
        msg = "The data is too small to cross-validate any component."
        raise ValueError(msg)
    a_max = upper if max_components is None else min(int(max_components), upper)
    a_max = max(1, a_max)

    folds = KFold(n_splits=n_splits, shuffle=True, random_state=_RANDOM_STATE)
    press_cv = np.zeros(a_max)
    for train_idx, test_idx in folds.split(x):
        x_train = x_block.iloc[train_idx]
        y_train = y_block.iloc[train_idx] if (kind == "PLS" and y_block is not None) else None
        weights, loadings = _weights_and_loadings(x_train, y_train, kind, a_max)
        press_cv += _press_curve(weights, loadings, x[test_idx], target[test_idx], a_max)

    # Calibration PRESS from a single full-data fit, same reconstruction math.
    full_weights, full_loadings = _weights_and_loadings(
        x_block,
        y_block if kind == "PLS" else None,
        kind,
        a_max,
    )
    press_cal = _press_curve(full_weights, full_loadings, x, target, a_max)

    total_ss = float(np.nansum((target - np.nanmean(target, axis=0)) ** 2))
    if total_ss <= 0:
        msg = "The target block has no variance to cross-validate."
        raise ValueError(msg)

    r2 = [float(1.0 - p / total_ss) for p in press_cal]
    q2 = [float(1.0 - p / total_ss) for p in press_cv]
    r2_per = [r2[i] - (r2[i - 1] if i else 0.0) for i in range(a_max)]
    q2_per = [q2[i] - (q2[i - 1] if i else 0.0) for i in range(a_max)]
    # Prefer the fewest components whose Q2 is within tolerance of the best: the
    # most parsimonious model that predicts essentially as well as the peak.
    threshold = max(q2) - _Q2_TOLERANCE
    recommended = next(a for a, value in enumerate(q2, start=1) if value >= threshold)

    return CrossValidation(
        kind=kind,
        target="Y" if kind == "PLS" else "X",
        n_splits=n_splits,
        component_numbers=list(range(1, a_max + 1)),
        r2=r2,
        q2=q2,
        r2_per_component=r2_per,
        q2_per_component=q2_per,
        recommended=recommended,
    )
