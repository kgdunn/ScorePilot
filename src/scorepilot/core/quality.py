"""Data-quality checks over a raw dataset.

Pure functions that report problems a user should resolve before modelling:
non-unique primary identifiers, invalid (non-numeric) values in quantitative
columns, and missing data beyond a tolerance. Nothing here mutates the data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from scorepilot.core._pandas import column as get_column
from scorepilot.core._pandas import to_numeric
from scorepilot.core.schema import ColumnType


@dataclass(frozen=True)
class ColumnQuality:
    """Quality summary for one column."""

    name: str
    n_missing: int
    pct_missing: float
    n_invalid: int
    invalid_rows: list[int]
    exceeds_tolerance: bool


@dataclass(frozen=True)
class ObservationQuality:
    """Quality summary for one observation (row) that exceeds the tolerance."""

    index: int
    identifier: str | None
    n_missing: int
    pct_missing: float


@dataclass(frozen=True)
class DuplicateIdentifier:
    """A primary-identifier value shared by more than one observation."""

    value: str
    rows: list[int]


@dataclass(frozen=True)
class QualityReport:
    """Aggregate data-quality report for a dataset."""

    n_rows: int
    n_columns: int
    n_missing_cells: int
    pct_missing: float
    primary_id_unique: bool
    duplicate_primary_ids: list[DuplicateIdentifier]
    columns: list[ColumnQuality]
    observations_exceeding: list[ObservationQuality] = field(default_factory=list)


def quality_report(
    df: pd.DataFrame,
    *,
    types: dict[str, ColumnType],
    primary_id: str | None = None,
    variable_tolerance: float = 0.5,
    observation_tolerance: float = 0.5,
) -> QualityReport:
    """Compute a :class:`QualityReport` for ``df``.

    Parameters
    ----------
    df
        The raw dataset (all columns, original dtypes).
    types
        Mapping from column name to :class:`ColumnType`. Only quantitative columns
        are checked for invalid (non-numeric) values.
    primary_id
        Name of the column that uniquely identifies observations, if any.
    variable_tolerance, observation_tolerance
        Fractions in ``[0, 1]``. A column or observation whose missing fraction
        exceeds its tolerance is flagged.
    """
    n_rows, n_columns = int(df.shape[0]), int(df.shape[1])
    missing_mask = df.isna()

    columns = [
        _column_quality(
            get_column(df, str(name)),
            get_column(missing_mask, str(name)),
            types.get(str(name)),
            variable_tolerance,
        )
        for name in df.columns
    ]

    n_missing_cells = int(missing_mask.to_numpy().sum())
    total_cells = n_rows * n_columns
    pct_missing = (100.0 * n_missing_cells / total_cells) if total_cells else 0.0

    observations_exceeding = _observations_exceeding(
        df, missing_mask, primary_id, observation_tolerance
    )
    duplicates = _duplicate_identifiers(df, primary_id)

    return QualityReport(
        n_rows=n_rows,
        n_columns=n_columns,
        n_missing_cells=n_missing_cells,
        pct_missing=pct_missing,
        primary_id_unique=len(duplicates) == 0,
        duplicate_primary_ids=duplicates,
        columns=columns,
        observations_exceeding=observations_exceeding,
    )


def _column_quality(
    column: pd.Series,
    missing: pd.Series,
    column_type: ColumnType | None,
    tolerance: float,
) -> ColumnQuality:
    n_missing = int(missing.sum())
    total = len(column)
    pct_missing = (100.0 * n_missing / total) if total else 0.0

    invalid_rows: list[int] = []
    if column_type is ColumnType.QUANTITATIVE:
        coerced = to_numeric(column)
        invalid = coerced.isna() & ~missing
        invalid_rows = [int(i) for i in range(total) if bool(invalid.iloc[i])]

    return ColumnQuality(
        name=str(column.name),
        n_missing=n_missing,
        pct_missing=pct_missing,
        n_invalid=len(invalid_rows),
        invalid_rows=invalid_rows,
        exceeds_tolerance=pct_missing > tolerance * 100,
    )


def _observations_exceeding(
    df: pd.DataFrame,
    missing_mask: pd.DataFrame,
    primary_id: str | None,
    tolerance: float,
) -> list[ObservationQuality]:
    if df.shape[1] == 0:
        return []
    per_row_missing = missing_mask.sum(axis=1)
    threshold = tolerance * df.shape[1]
    out: list[ObservationQuality] = []
    for position, count in enumerate(per_row_missing):
        if count <= threshold:
            continue
        identifier = None if primary_id is None else _safe_str(df.iloc[position][primary_id])
        out.append(
            ObservationQuality(
                index=position,
                identifier=identifier,
                n_missing=int(count),
                pct_missing=100.0 * int(count) / df.shape[1],
            )
        )
    return out


def _duplicate_identifiers(df: pd.DataFrame, primary_id: str | None) -> list[DuplicateIdentifier]:
    if primary_id is None or primary_id not in df.columns:
        return []
    column = get_column(df, primary_id)
    duplicated_values = column.loc[column.duplicated(keep=False)].dropna().unique()
    out: list[DuplicateIdentifier] = []
    for value in duplicated_values:
        rows = [int(i) for i in range(len(column)) if column.iloc[i] == value]
        out.append(DuplicateIdentifier(value=_safe_str(value) or "", rows=rows))
    return out


def _safe_str(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value)
