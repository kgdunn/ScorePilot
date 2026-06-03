"""Preprocessing helpers used before fitting a model.

Thin, dependency-light wrappers over ``process_improve``'s scaling utilities.
Returning the fitted scaler alongside the transformed frame lets callers apply
the identical transform to new data later.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd
from process_improve.multivariate import MCUVScaler


class Preprocessing(StrEnum):
    """Supported preprocessing of the X block before fitting.

    Attributes
    ----------
    NONE
        Use the data as-is.
    MEAN_CENTER_SCALE
        Mean-center and scale each column to unit variance (autoscaling), the
        standard preprocessing for PCA/PLS in chemometrics.
    """

    NONE = "none"
    MEAN_CENTER_SCALE = "mean_center_scale"


@dataclass(frozen=True)
class Prepared:
    """Result of preparing a data block.

    Attributes
    ----------
    data
        The transformed DataFrame, ready to fit.
    scaler
        The fitted ``MCUVScaler``, or ``None`` when ``preprocessing`` is
        :attr:`Preprocessing.NONE`. Apply it to new data with ``scaler.transform``.
    preprocessing
        The preprocessing that was applied.
    """

    data: pd.DataFrame
    scaler: MCUVScaler | None
    preprocessing: Preprocessing


def prepare(
    data: pd.DataFrame,
    preprocessing: Preprocessing = Preprocessing.MEAN_CENTER_SCALE,
) -> Prepared:
    """Apply the requested preprocessing to a data block.

    Parameters
    ----------
    data
        The raw X block, observations in rows and variables in columns.
    preprocessing
        Which preprocessing to apply. Defaults to mean-center and unit-variance
        scaling (autoscaling).

    Returns
    -------
    Prepared
        The transformed data and the fitted scaler (if any).
    """
    if preprocessing is Preprocessing.NONE:
        return Prepared(data=data, scaler=None, preprocessing=preprocessing)

    scaler = MCUVScaler().fit(data)
    transformed = scaler.transform(data)
    return Prepared(data=transformed, scaler=scaler, preprocessing=preprocessing)
