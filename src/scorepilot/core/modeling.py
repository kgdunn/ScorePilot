"""Fit a PCA or PLS model and extract its diagnostics.

Wraps ``process_improve``'s PCA/PLS estimators and pulls out the arrays a model
view needs: scores, loadings, explained variance, R2, Hotelling's T2, SPE, their
control limits, the T2 confidence ellipse, and VIP. Pure over DataFrames.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np
import pandas as pd
from process_improve.multivariate import PCA, PLS, vip

ModelKind = str  # "PCA" or "PLS"


@dataclass(frozen=True)
class ModelDiagnostics:
    """Everything needed to display a fitted model."""

    kind: ModelKind
    n_components: int
    conf_level: float
    component_names: list[str]
    observation_names: list[str]
    x_variable_names: list[str]
    y_variable_names: list[str]
    scores: pd.DataFrame
    x_loadings: pd.DataFrame
    y_loadings: pd.DataFrame | None
    explained_variance: np.ndarray
    r2_per_component: list[float]
    r2_cumulative: list[float]
    hotellings_t2: pd.Series
    spe: pd.Series
    t2_limit: float
    spe_limit: float
    ellipse_x: list[float]
    ellipse_y: list[float]
    vip: dict[str, float]


def _fit_estimator(
    x_block: pd.DataFrame,
    y_block: pd.DataFrame | None,
    kind: ModelKind,
    n_components: int,
) -> PCA | PLS:
    """Validate inputs and fit the underlying PCA/PLS estimator.

    Raises
    ------
    ValueError
        For an unknown ``kind``, a PLS fit without Y columns, or an out-of-range
        ``n_components``.
    """
    max_components = min(x_block.shape)
    if not 1 <= n_components <= max_components:
        msg = (
            f"n_components must be between 1 and {max_components} for X of shape "
            f"{x_block.shape}, got {n_components}"
        )
        raise ValueError(msg)

    if kind == "PLS":
        if y_block is None or y_block.shape[1] == 0:
            msg = "PLS requires at least one Y column."
            raise ValueError(msg)
        return PLS(n_components=n_components, scale=False).fit(x_block, y_block)
    if kind == "PCA":
        return PCA(n_components=n_components).fit(x_block)
    msg = f"Unknown model kind: {kind!r} (expected 'PCA' or 'PLS')"
    raise ValueError(msg)


def fit_model(
    x_block: pd.DataFrame,
    y_block: pd.DataFrame | None,
    kind: ModelKind,
    n_components: int,
    *,
    conf_level: float = 0.95,
    observation_names: list[str] | None = None,
) -> ModelDiagnostics:
    """Fit a model of ``kind`` ("PCA" or "PLS") to already-preprocessed blocks.

    ``x_block`` (and ``y_block`` for PLS) are expected to be the output of
    ``apply_spec`` - transformed, centered, and scaled - so the estimators are not
    asked to scale again.

    ``observation_names`` labels the rows in plots (the scores scatter, T2/SPE
    bars). When omitted the block's index is used; callers with a primary
    identifier should pass its values so points carry meaningful labels rather
    than positional integers.

    Raises
    ------
    ValueError
        For an unknown ``kind``, a PLS fit without Y columns, an out-of-range
        ``n_components``, or an ``observation_names`` length mismatch.
    """
    if observation_names is not None and len(observation_names) != x_block.shape[0]:
        msg = (
            f"observation_names has {len(observation_names)} entries but the X block "
            f"has {x_block.shape[0]} rows"
        )
        raise ValueError(msg)
    model = _fit_estimator(x_block, y_block, kind, n_components)
    if kind == "PLS":
        x_loadings = cast("pd.DataFrame", model.x_loadings_)
        y_loadings: pd.DataFrame | None = cast("pd.DataFrame", model.y_loadings_)
    else:
        x_loadings = cast("pd.DataFrame", model.loadings_)
        y_loadings = None

    component_names = [f"PC{i}" for i in range(1, n_components + 1)]
    scores = cast("pd.DataFrame", model.scores_).copy()
    scores.columns = component_names
    x_loadings = x_loadings.copy()
    x_loadings.columns = component_names

    r2_cumulative = [float(v) for v in np.asarray(model.r2_cumulative_)]
    r2_per_component = [
        r2_cumulative[i] - (r2_cumulative[i - 1] if i else 0.0) for i in range(len(r2_cumulative))
    ]

    if n_components >= 2:
        ex, ey = model.ellipse_coordinates(1, 2, conf_level=conf_level, n_points=100)
        ellipse_x = [float(v) for v in ex]
        ellipse_y = [float(v) for v in ey]
    else:
        ellipse_x, ellipse_y = [], []

    vip_series = vip(model)
    vip_map = {str(k): float(v) for k, v in vip_series.items()}

    if y_loadings is not None:
        y_loadings = y_loadings.copy()
        y_loadings.columns = component_names

    return ModelDiagnostics(
        kind=kind,
        n_components=n_components,
        conf_level=conf_level,
        component_names=component_names,
        observation_names=(
            observation_names
            if observation_names is not None
            else [str(i) for i in x_block.index.astype(str)]
        ),
        x_variable_names=[str(c) for c in x_block.columns.astype(str)],
        y_variable_names=[str(c) for c in (y_block.columns if y_block is not None else [])],
        scores=scores,
        x_loadings=x_loadings,
        y_loadings=y_loadings,
        explained_variance=np.asarray(model.explained_variance_, dtype=float),
        r2_per_component=r2_per_component,
        r2_cumulative=r2_cumulative,
        hotellings_t2=model.hotellings_t2_.iloc[:, -1].rename("hotellings_t2"),
        spe=model.spe_.iloc[:, -1].rename("spe"),
        t2_limit=float(model.hotellings_t2_limit(conf_level=conf_level)),
        spe_limit=float(model.spe_limit(conf_level=conf_level)),
        ellipse_x=ellipse_x,
        ellipse_y=ellipse_y,
        vip=vip_map,
    )


@dataclass(frozen=True)
class Contributions:
    """Per-variable contributions of one observation to T2 and SPE."""

    observation: int
    observation_name: str
    variable_names: list[str]
    t2: list[float]
    spe: list[float]


def observation_contributions(
    x_block: pd.DataFrame,
    y_block: pd.DataFrame | None,
    kind: ModelKind,
    n_components: int,
    observation: int,
    *,
    observation_name: str | None = None,
) -> Contributions:
    """Per-variable contributions of one observation to Hotelling's T2 and SPE.

    The T2 contributions sum to that observation's T2; the SPE contributions are
    its signed per-variable residuals (their squares sum to its SPE). ``x_block``
    (and ``y_block`` for PLS) must be the preprocessed blocks from ``apply_spec``.
    ``observation_name`` labels the observation (e.g. its primary identifier);
    when omitted the block's index value is used.

    Raises
    ------
    ValueError
        For an out-of-range ``observation`` index, or any error from the fit.
    """
    n_rows = x_block.shape[0]
    if not 0 <= observation < n_rows:
        msg = f"observation must be between 0 and {n_rows - 1}, got {observation}"
        raise ValueError(msg)

    model = _fit_estimator(x_block, y_block, kind, n_components)
    # Delegate the per-variable T2 / SPE decomposition to process_improve so the
    # MSPC math lives in one place (process_improve >= 1.27.0). Each call returns
    # an (n_observations x n_variables) frame; we pick out the requested row. The
    # T2 contributions sum to the observation's T2; the SPE contributions are its
    # signed residuals whose squares sum to its SPE.
    t2_row = model.t2_contributions(x_block).iloc[observation]
    spe_row = model.spe_contributions(x_block).iloc[observation]

    return Contributions(
        observation=observation,
        observation_name=(
            observation_name if observation_name is not None else str(x_block.index[observation])
        ),
        variable_names=[str(c) for c in x_block.columns.astype(str)],
        t2=[float(v) for v in t2_row],
        spe=[float(v) for v in spe_row],
    )
