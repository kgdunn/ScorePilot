"""Per-variable transforms used in preprocessing recipes and previews.

Pure functions over a pandas Series. Out-of-domain inputs (for example, a
non-positive value passed to ``log``) become ``NaN`` rather than raising, so a
preview never fails on messy data. Transforms never mutate their input.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scorepilot.core._pandas import to_numeric
from scorepilot.core.schema import TransformKind


def apply_transform(
    series: pd.Series,
    kind: TransformKind,
    *,
    c1: float = 0.0,
    c2: float = 1.0,
) -> pd.Series:
    """Apply a transform to a numeric series.

    Parameters
    ----------
    series
        The numeric values to transform. Non-numeric entries are coerced to
        ``NaN`` first.
    kind
        Which transform to apply.
    c1, c2
        Transform constants. Their meaning depends on ``kind`` (see Notes); the
        defaults reproduce the textbook form of each transform.

    Returns
    -------
    pandas.Series
        The transformed values, aligned to the input index. Out-of-domain values
        are ``NaN``.

    Notes
    -----
    - ``none``: ``x``
    - ``linear``: ``c2 * x + c1`` (defaults: identity)
    - ``log``: ``log(x + c1)`` (natural log; defined for ``x + c1 > 0``)
    - ``neglog``: ``sign(x) * log1p(abs(x))`` (sign-symmetric log)
    - ``logit``: ``log(p / (1 - p))`` with ``p = x`` (defined for ``0 < x < 1``)
    - ``exponential``: ``exp(x)``
    - ``power``: ``sign(x) * abs(x) ** c1`` (default ``c1 = 0.5``, i.e. signed root)
    """
    values = to_numeric(series).astype(float).to_numpy()

    with np.errstate(divide="ignore", invalid="ignore"):
        out = _transform_values(values, kind, c1=c1, c2=c2)

    out = np.where(np.isfinite(out), out, np.nan)
    return pd.Series(out, index=series.index, name=series.name)


def _transform_values(x: np.ndarray, kind: TransformKind, *, c1: float, c2: float) -> np.ndarray:
    match kind:
        case TransformKind.NONE:
            return x
        case TransformKind.LINEAR:
            return c2 * x + c1
        case TransformKind.LOG:
            return np.log(x + c1)
        case TransformKind.NEGLOG:
            return np.sign(x) * np.log1p(np.abs(x))
        case TransformKind.LOGIT:
            return np.log(x / (1.0 - x))
        case TransformKind.EXPONENTIAL:
            return np.exp(x)
        case TransformKind.POWER:
            exponent = c1 if c1 != 0.0 else 0.5
            return np.sign(x) * np.abs(x) ** exponent
    msg = f"Unknown transform kind: {kind}"  # pragma: no cover - exhaustive match
    raise ValueError(msg)
