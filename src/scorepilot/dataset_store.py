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

import numpy as np
import pandas as pd

from scorepilot.core import ColumnType, IdentifierRole, infer_column_type
from scorepilot.core._pandas import column as get_column
from scorepilot.core._pandas import to_numeric

SYNTHETIC_ID_NAME = "Row"


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
        # Identifier / class columns are intrinsic metadata, not model variables,
        # so they are excluded from the default X block even if numeric.
        return [
            c.name
            for c in self.columns
            if c.column_type is ColumnType.QUANTITATIVE and c.identifier_role is IdentifierRole.NONE
        ]


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
    """Infer each column's data type (no identifier roles assigned)."""
    return [
        ColumnMeta(name=str(name), column_type=infer_column_type(series))
        for name, series in frame.items()
    ]


def is_valid_primary(series: pd.Series) -> bool:
    """Whether a column can serve as a primary identifier: complete and unique."""
    return bool(series.notna().all()) and bool(series.is_unique)


def _is_primary_candidate(series: pd.Series, column_type: ColumnType) -> bool:
    """Whether a column is a plausible auto-detected primary identifier.

    Label-like columns (qualitative/datetime/unknown) qualify when complete and
    unique. Numeric columns qualify only when integer-valued: unique floats are
    almost always measurements, not identifiers.
    """
    if not is_valid_primary(series):
        return False
    if column_type is not ColumnType.QUANTITATIVE:
        return True
    numeric = to_numeric(series).to_numpy(dtype=float)
    return bool(np.isfinite(numeric).all()) and bool(np.all(numeric == np.round(numeric)))


def _unique_name(base: str, existing: pd.Index) -> str:
    """Return ``base``, or ``base_1``/``base_2``/... if it clashes with a column."""
    taken = {str(name) for name in existing}
    if base not in taken:
        return base
    index = 1
    while f"{base}_{index}" in taken:
        index += 1
    return f"{base}_{index}"


def prepare_dataset(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[ColumnMeta]]:
    """Infer column metadata and pick (or synthesize) a primary identifier.

    The primary identifier is the leftmost complete, unique, label-like or
    integer column. If no column qualifies, a synthetic ``Row`` column (1, 2, 3,
    ...) is inserted as the leftmost column and used as the primary identifier, so
    every dataset has a stable identifier. Returns the (possibly augmented) frame
    alongside its column metadata.
    """
    columns = infer_columns(frame)
    for meta in columns:
        if _is_primary_candidate(get_column(frame, meta.name), meta.column_type):
            meta.identifier_role = IdentifierRole.PRIMARY
            return frame, columns

    name = _unique_name(SYNTHETIC_ID_NAME, frame.columns)
    augmented = frame.copy()
    augmented.insert(0, name, range(1, len(augmented) + 1))
    columns.insert(
        0,
        ColumnMeta(
            name=name,
            column_type=ColumnType.QUALITATIVE,
            identifier_role=IdentifierRole.PRIMARY,
        ),
    )
    return augmented, columns


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
