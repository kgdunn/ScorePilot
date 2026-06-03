"""In-memory datasets and their column metadata.

A dataset is the immutable raw table plus intrinsic metadata: each column's data
type and (optionally) its identifier role. Modelling choices - X/Y, exclusions,
transforms, scaling - are *not* stored here; they live in a ``PreprocessingSpec``
per model variant. Datasets currently live in process memory; the same interface
can later be backed by a database without changing callers.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import cast
from uuid import uuid4

import pandas as pd

from scorepilot.core import ColumnType, IdentifierRole, infer_column_type


@dataclass
class ColumnMeta:
    """Intrinsic metadata for one column."""

    name: str
    column_type: ColumnType
    identifier_role: IdentifierRole = IdentifierRole.NONE


@dataclass
class Dataset:
    """An imported table and its column metadata."""

    id: str
    name: str
    raw: pd.DataFrame
    columns: list[ColumnMeta]
    source: str = "csv"
    sheet: str | None = None
    sheets: list[str] = field(default_factory=list)

    @property
    def n_rows(self) -> int:
        return int(self.raw.shape[0])

    @property
    def n_columns(self) -> int:
        return int(self.raw.shape[1])

    @property
    def primary_id(self) -> str | None:
        """Name of the primary-identifier column, if one is set."""
        for meta in self.columns:
            if meta.identifier_role is IdentifierRole.PRIMARY:
                return meta.name
        return None

    def column(self, name: str) -> ColumnMeta | None:
        return next((c for c in self.columns if c.name == name), None)

    def types(self) -> dict[str, ColumnType]:
        return {c.name: c.column_type for c in self.columns}

    def quantitative_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.column_type is ColumnType.QUANTITATIVE]


def load_table(
    content: bytes, filename: str, sheet: str | None = None
) -> tuple[pd.DataFrame, str, list[str], str | None]:
    """Parse uploaded file bytes into a DataFrame.

    Returns ``(frame, source, sheet_names, sheet_used)``. CSV files have no sheets.
    """
    lowered = filename.lower()
    if lowered.endswith((".xlsx", ".xls")):
        workbook = pd.ExcelFile(io.BytesIO(content))
        sheet_names = [str(s) for s in workbook.sheet_names]
        used = sheet if sheet in sheet_names else (sheet_names[0] if sheet_names else None)
        frame = workbook.parse(used) if used is not None else pd.DataFrame()
        return cast("pd.DataFrame", frame), "excel", sheet_names, used
    frame = pd.read_csv(io.BytesIO(content))
    return frame, "csv", [], None


def _infer_columns(frame: pd.DataFrame) -> list[ColumnMeta]:
    columns = [
        ColumnMeta(name=str(name), column_type=infer_column_type(series))
        for name, series in frame.items()
    ]
    _assign_default_primary(frame, columns)
    return columns


def _assign_default_primary(frame: pd.DataFrame, columns: list[ColumnMeta]) -> None:
    """Mark the first fully-unique label-like column as the primary identifier."""
    for meta in columns:
        series = cast("pd.Series", frame[meta.name])
        is_label = meta.column_type in (ColumnType.QUALITATIVE, ColumnType.DATETIME)
        if is_label and bool(series.notna().all()) and bool(series.is_unique):
            meta.identifier_role = IdentifierRole.PRIMARY
            return


class DatasetStore:
    """A process-wide registry of imported datasets."""

    def __init__(self) -> None:
        self._datasets: dict[str, Dataset] = {}

    def add(
        self,
        name: str,
        frame: pd.DataFrame,
        *,
        source: str = "csv",
        sheets: list[str] | None = None,
        sheet: str | None = None,
    ) -> Dataset:
        dataset = Dataset(
            id=uuid4().hex,
            name=name,
            raw=frame,
            columns=_infer_columns(frame),
            source=source,
            sheet=sheet,
            sheets=sheets or [],
        )
        self._datasets[dataset.id] = dataset
        return dataset

    def get(self, dataset_id: str) -> Dataset | None:
        return self._datasets.get(dataset_id)

    def list(self) -> list[Dataset]:
        return list(self._datasets.values())
