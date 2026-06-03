"""Single-variable profiling: type inference, summary stats, histogram, sequence.

These pure helpers back the data-quality checks and the variable inspector. They
describe a column as it is; they do not transform or model it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from process_improve.univariate.metrics import summary_stats
from scipy.stats import skew

from scorepilot.core._pandas import to_datetime, to_numeric
from scorepilot.core.schema import ColumnType, TransformKind

_TEXT_PARSE_THRESHOLD = 0.8


def infer_column_type(series: pd.Series) -> ColumnType:
    """Infer whether a column is quantitative, qualitative, or a date/time.

    Numeric and boolean dtypes are decided directly. For text columns we try to
    parse the non-missing values as numbers, then as dates; a column is treated as
    quantitative or datetime only if at least 80% of its values parse.
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        return ColumnType.DATETIME
    if pd.api.types.is_bool_dtype(series):
        return ColumnType.QUALITATIVE
    if pd.api.types.is_numeric_dtype(series):
        return ColumnType.QUANTITATIVE

    non_missing = series.dropna()
    if non_missing.empty:
        return ColumnType.UNKNOWN

    numeric_frac = to_numeric(non_missing).notna().mean()
    if numeric_frac >= _TEXT_PARSE_THRESHOLD:
        return ColumnType.QUANTITATIVE

    datetime_frac = to_datetime(non_missing).notna().mean()
    if datetime_frac >= _TEXT_PARSE_THRESHOLD:
        return ColumnType.DATETIME

    return ColumnType.QUALITATIVE


@dataclass(frozen=True)
class VariableSummary:
    """Descriptive summary of a single variable.

    Numeric fields are ``None`` for non-quantitative columns.
    """

    name: str
    column_type: ColumnType
    n: int
    n_missing: int
    pct_missing: float
    n_unique: int
    mean: float | None = None
    std: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    median: float | None = None
    q25: float | None = None
    q75: float | None = None
    skewness: float | None = None
    min_max_ratio: float | None = None


def variable_summary(series: pd.Series, column_type: ColumnType | None = None) -> VariableSummary:
    """Compute a :class:`VariableSummary` for one column."""
    column_type = column_type or infer_column_type(series)
    total = len(series)
    n_missing = int(series.isna().sum())
    n = total - n_missing
    pct_missing = (100.0 * n_missing / total) if total else 0.0
    name = str(series.name) if series.name is not None else ""
    n_unique = int(series.dropna().nunique())

    if column_type is not ColumnType.QUANTITATIVE or n == 0:
        return VariableSummary(
            name=name,
            column_type=column_type,
            n=n,
            n_missing=n_missing,
            pct_missing=pct_missing,
            n_unique=n_unique,
        )

    numeric = to_numeric(series)
    stats = summary_stats(numeric, method="regular")
    minimum = float(stats["min"])
    maximum = float(stats["max"])
    skewness = float(skew(numeric.to_numpy(), nan_policy="omit"))
    min_max_ratio = maximum / minimum if minimum > 0 else None

    return VariableSummary(
        name=name,
        column_type=column_type,
        n=n,
        n_missing=n_missing,
        pct_missing=pct_missing,
        n_unique=n_unique,
        mean=float(stats["mean"]),
        std=float(stats["std_ddof1"]),
        minimum=minimum,
        maximum=maximum,
        median=float(stats["median"]),
        q25=float(stats["percentile_25"]),
        q75=float(stats["percentile_75"]),
        skewness=skewness,
        min_max_ratio=min_max_ratio,
    )


def histogram(series: pd.Series, bins: int = 20) -> tuple[list[float], list[float]]:
    """Return ``(counts, edges)`` for a frequency histogram of a numeric column.

    Empty or all-missing columns return empty lists.
    """
    numeric = to_numeric(series).dropna().to_numpy()
    if numeric.size == 0:
        return [], []
    counts, edges = np.histogram(numeric, bins=bins)
    return counts.astype(int).tolist(), edges.astype(float).tolist()


def sequence(series: pd.Series) -> list[float | None]:
    """Return the column's numeric values in order (missing values as ``None``).

    Useful for plotting a variable against acquisition order.
    """
    numeric = to_numeric(series)
    return [None if pd.isna(v) else float(v) for v in numeric]


def suggest_transform(summary: VariableSummary) -> TransformKind:
    """Suggest a transform from a variable's shape.

    A strongly right-skewed, strictly positive variable with a wide dynamic range
    is a candidate for a log transform; a milder skew suggests a signed power
    (root). Otherwise no transform is suggested.
    """
    if summary.column_type is not ColumnType.QUANTITATIVE or summary.skewness is None:
        return TransformKind.NONE
    strongly_skewed = summary.skewness > 1.0
    positive = summary.minimum is not None and summary.minimum > 0
    wide_range = summary.min_max_ratio is not None and summary.min_max_ratio > 20
    if strongly_skewed and positive and wide_range:
        return TransformKind.LOG
    if strongly_skewed:
        return TransformKind.POWER
    return TransformKind.NONE
