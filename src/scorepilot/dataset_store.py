"""Datasets and their column metadata.

A dataset is the immutable raw table plus intrinsic metadata: each column's data
type and (optionally) its identifier role. Modelling choices - X/Y, exclusions,
transforms, scaling - are *not* stored here; they live in a ``PreprocessingSpec``
per model variant.

The :class:`Dataset` dataclass is the in-process working object. Persistence is
handled by the repository in ``db`` (a ``dataset`` table) using the serialization
helpers here: the raw table is stored as gzipped CSV and read back with the
round-trip float parser so values survive a restart exactly.
"""

from __future__ import annotations

import gzip
import io
from dataclasses import dataclass, field
from typing import cast

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


def infer_columns(frame: pd.DataFrame) -> list[ColumnMeta]:
    """Infer column metadata for a freshly imported frame."""
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


def serialize_frame(frame: pd.DataFrame) -> bytes:
    """Serialize a raw table to a gzipped CSV blob for storage."""
    return gzip.compress(frame.to_csv(index=False).encode())


def deserialize_frame(blob: bytes) -> pd.DataFrame:
    """Restore a raw table from a :func:`serialize_frame` blob.

    ``float_precision="round_trip"`` makes pandas parse floats with a correctly
    rounded parser, so the values match the originally imported frame exactly.
    """
    buffer = io.BytesIO(gzip.decompress(blob))
    return pd.read_csv(buffer, float_precision="round_trip")


def column_to_dict(meta: ColumnMeta) -> dict[str, str]:
    """Serialize column metadata to a JSON-friendly dict."""
    return {
        "name": meta.name,
        "column_type": meta.column_type.value,
        "identifier_role": meta.identifier_role.value,
    }


def column_from_dict(data: dict[str, str]) -> ColumnMeta:
    """Restore column metadata from :func:`column_to_dict`."""
    return ColumnMeta(
        name=data["name"],
        column_type=ColumnType(data["column_type"]),
        identifier_role=IdentifierRole(data["identifier_role"]),
    )
