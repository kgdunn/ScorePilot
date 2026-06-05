"""Dataset import and metadata endpoints.

Datasets can be imported from an uploaded file or fetched from a URL, and are
persisted by the dataset repository. Import keeps every column (identifiers and
qualitative columns included) and infers each column's data type. Roles like X/Y
and exclusions are *not* set here - those are modelling choices captured in a
preprocessing spec.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from scorepilot.api.deps import DatasetStoreDep
from scorepilot.core import IdentifierRole
from scorepilot.core._pandas import column as get_column
from scorepilot.dataset_store import Dataset, is_valid_primary, load_table
from scorepilot.samples import SAMPLES, get_sample, load_sample_frame
from scorepilot.schemas import (
    ColumnMetaModel,
    ColumnUpdate,
    DatasetDetail,
    DatasetUrlRequest,
    SampleInfo,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])

# Cap remote imports so a huge URL cannot exhaust memory.
MAX_URL_BYTES = 5 * 1024 * 1024


def to_detail(dataset: Dataset) -> DatasetDetail:
    """Build the API detail model for a dataset."""
    return DatasetDetail(
        dataset_id=dataset.id,
        name=dataset.name,
        source=dataset.source,
        sheet=dataset.sheet,
        sheets=dataset.sheets,
        n_rows=dataset.n_rows,
        n_columns=dataset.n_columns,
        primary_id=dataset.primary_id,
        columns=[
            ColumnMetaModel(
                name=c.name,
                column_type=c.column_type,
                identifier_role=c.identifier_role,
            )
            for c in dataset.columns
        ],
    )


@router.post("", response_model=DatasetDetail, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    store: DatasetStoreDep,
    file: Annotated[UploadFile, File(description="A CSV or Excel file")],
    sheet: Annotated[str | None, Query(description="Excel sheet name")] = None,
) -> DatasetDetail:
    """Import a CSV or Excel file as a dataset."""
    raw = await file.read()
    filename = file.filename or "dataset.csv"
    try:
        frame, source, sheets, used = load_table(raw, filename, sheet)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse file: {exc}",
        ) from exc

    if frame.shape[1] == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No columns found in the uploaded file.",
        )

    dataset = store.add(filename, frame, source=source, sheets=sheets, sheet=used)
    return to_detail(dataset)


def _fetch_url(url: str) -> tuple[bytes, str]:
    """Fetch a CSV/Excel file from ``url`` (<= 5 MB), returning bytes and filename.

    Only ``http``/``https`` URLs are allowed, and the download is capped so a huge
    file cannot exhaust memory.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must start with http:// or https://.",
        )
    filename = Path(parsed.path).name or "dataset.csv"
    request = urllib.request.Request(url, headers={"User-Agent": "ScorePilot"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            declared = response.headers.get("Content-Length")
            if declared is not None and declared.isdigit() and int(declared) > MAX_URL_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="That file is larger than the 5 MB limit.",
                )
            chunks: list[bytes] = []
            total = 0
            while chunk := response.read(65536):
                total += len(chunk)
                if total > MAX_URL_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="That file is larger than the 5 MB limit.",
                    )
                chunks.append(chunk)
    except HTTPException:
        raise
    except (urllib.error.URLError, ValueError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not fetch the URL: {exc}",
        ) from exc
    return b"".join(chunks), filename


@router.post("/from-url", response_model=DatasetDetail, status_code=status.HTTP_201_CREATED)
def open_dataset_from_url(request: DatasetUrlRequest, store: DatasetStoreDep) -> DatasetDetail:
    """Import a dataset from a CSV/Excel file at a public URL (max 5 MB)."""
    content, filename = _fetch_url(request.url)
    try:
        frame, _source, sheets, used = load_table(content, filename, request.sheet)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse file: {exc}",
        ) from exc

    if frame.shape[1] == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No columns found in the fetched file.",
        )

    dataset = store.add(filename, frame, source="url", sheets=sheets, sheet=used)
    return to_detail(dataset)


@router.get("", response_model=list[DatasetDetail])
def list_datasets(store: DatasetStoreDep) -> list[DatasetDetail]:
    """List all imported datasets."""
    return [to_detail(d) for d in store.list()]


@router.get("/samples", response_model=list[SampleInfo])
def list_samples() -> list[SampleInfo]:
    """List the bundled demo datasets."""
    return [
        SampleInfo(name=s.name, title=s.title, description=s.description, source_url=s.source_url)
        for s in SAMPLES
    ]


@router.post("/samples/{name}", response_model=DatasetDetail, status_code=status.HTTP_201_CREATED)
def load_sample(name: str, store: DatasetStoreDep) -> DatasetDetail:
    """Import a bundled demo dataset into the store."""
    sample = get_sample(name)
    if sample is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown sample: {name}",
        )
    dataset = store.add(sample.title, load_sample_frame(sample), source="sample")
    return to_detail(dataset)


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(dataset_id: str, store: DatasetStoreDep) -> DatasetDetail:
    """Return one dataset's metadata."""
    return to_detail(_require(store, dataset_id))


@router.patch("/{dataset_id}/columns/{column}", response_model=DatasetDetail)
def update_column(
    dataset_id: str, column: str, update: ColumnUpdate, store: DatasetStoreDep
) -> DatasetDetail:
    """Update a column's data type or identifier role."""
    dataset = _require(store, dataset_id)
    meta = dataset.column(column)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown column: {column}",
        )

    if update.column_type is not None:
        meta.column_type = update.column_type
    if update.identifier_role is not None:
        if update.identifier_role is IdentifierRole.PRIMARY:
            series = get_column(dataset.raw, column)
            if not is_valid_primary(series):
                n_missing = int(series.isna().sum())
                n_duplicate = int(series.duplicated().sum())
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Column '{column}' cannot be the primary identifier: it must have "
                        f"unique, non-missing values ({n_missing} missing, "
                        f"{n_duplicate} duplicate)."
                    ),
                )
            # Relinquish the previous primary: there can be only one.
            for other in dataset.columns:
                if other.identifier_role is IdentifierRole.PRIMARY:
                    other.identifier_role = IdentifierRole.NONE
        meta.identifier_role = update.identifier_role

    store.save(dataset)
    return to_detail(dataset)


def _require(store: DatasetStoreDep, dataset_id: str) -> Dataset:
    dataset = store.get(dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown dataset_id: {dataset_id}",
        )
    return dataset
