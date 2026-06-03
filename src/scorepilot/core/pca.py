"""PCA fitting, wrapping ``process_improve``'s estimator.

ScorePilot never reimplements the chemometrics math; this module adapts the
fitted ``process_improve`` PCA into a plain, serialization-friendly result object
made of numpy arrays and pandas objects, with no web/DB dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from process_improve.multivariate import PCA

from scorepilot.core.preprocessing import Preprocessing, prepare


@dataclass(frozen=True)
class PCAResult:
    """Outcome of fitting a PCA model.

    All fields are plain pandas/numpy objects so the result can be serialized or
    handed to an API layer without leaking the underlying estimator.

    Attributes
    ----------
    n_components
        Number of components extracted.
    preprocessing
        Preprocessing applied to the X block before fitting.
    conf_level
        Confidence level used for the T^2 and SPE limits.
    component_names
        Labels for the components, e.g. ``["PC1", "PC2"]``.
    observation_names, variable_names
        Row (observation) and column (variable) labels of the input.
    scores
        Score matrix T, shape ``(n_observations, n_components)``.
    loadings
        Loading matrix P, shape ``(n_variables, n_components)``.
    explained_variance
        Variance explained by each component, shape ``(n_components,)``.
    r2_cumulative
        Cumulative fraction of X variance explained after each component.
    hotellings_t2
        Hotelling's T^2 per observation using all components.
    spe
        Squared prediction error (DModX) per observation using all components.
    t2_limit, spe_limit
        Upper control limits for T^2 and SPE at ``conf_level``.
    """

    n_components: int
    preprocessing: Preprocessing
    conf_level: float
    component_names: list[str]
    observation_names: list[str]
    variable_names: list[str]
    scores: pd.DataFrame
    loadings: pd.DataFrame
    explained_variance: np.ndarray
    r2_cumulative: pd.Series
    hotellings_t2: pd.Series
    spe: pd.Series
    t2_limit: float
    spe_limit: float


def fit_pca(
    data: pd.DataFrame,
    n_components: int,
    *,
    preprocessing: Preprocessing = Preprocessing.MEAN_CENTER_SCALE,
    conf_level: float = 0.95,
) -> PCAResult:
    """Fit a PCA model to a data block.

    Parameters
    ----------
    data
        The X block: observations in rows, variables in columns. Column and row
        labels are preserved in the result.
    n_components
        Number of principal components to extract. Must be between 1 and
        ``min(n_observations, n_variables)``.
    preprocessing
        Preprocessing applied before fitting. Defaults to autoscaling
        (mean-center, unit variance).
    conf_level
        Confidence level (0 < conf_level < 1) for the T^2 and SPE limits.

    Returns
    -------
    PCAResult
        The fitted scores, loadings, diagnostics, and control limits.

    Raises
    ------
    ValueError
        If ``n_components`` is not a positive integer within the data's rank.
    """
    max_components = min(data.shape)
    if not 1 <= n_components <= max_components:
        msg = (
            f"n_components must be between 1 and {max_components} "
            f"for data of shape {data.shape}, got {n_components}"
        )
        raise ValueError(msg)

    prepared = prepare(data, preprocessing)
    model = PCA(n_components=n_components).fit(prepared.data)

    component_names = [f"PC{i}" for i in range(1, n_components + 1)]
    scores = model.scores_.copy()
    scores.columns = component_names
    loadings = model.loadings_.copy()
    loadings.columns = component_names

    # spe_ and hotellings_t2_ hold per-component columns; the final column uses
    # all fitted components.
    hotellings_t2 = model.hotellings_t2_.iloc[:, -1].rename("hotellings_t2")
    spe = model.spe_.iloc[:, -1].rename("spe")
    r2_cumulative = pd.Series(
        np.asarray(model.r2_cumulative_), index=component_names, name="r2_cumulative"
    )

    return PCAResult(
        n_components=n_components,
        preprocessing=prepared.preprocessing,
        conf_level=conf_level,
        component_names=component_names,
        observation_names=list(data.index.astype(str)),
        variable_names=list(data.columns.astype(str)),
        scores=scores,
        loadings=loadings,
        explained_variance=np.asarray(model.explained_variance_, dtype=float),
        r2_cumulative=r2_cumulative,
        hotellings_t2=hotellings_t2,
        spe=spe,
        t2_limit=float(model.hotellings_t2_limit(conf_level=conf_level)),
        spe_limit=float(model.spe_limit(conf_level=conf_level)),
    )
