"""Dataset import and metadata endpoints.

Uploaded datasets live in an in-memory store keyed by a generated id. Import keeps
every column (identifiers and qualitative columns included) and infers each
column's data type. Roles like X/Y and exclusions are *not* set here - those are
modelling choices captured in a preprocessing spec.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from scorepilot.api.deps import DatasetStoreDep
from scorepilot.core import IdentifierRole
from scorepilot.dataset_store import Dataset, load_table
from scorepilot.samples import SAMPLES, get_sample, load_sample_frame
from scorepilot.schemas import (
    ColumnMetaModel,
    ColumnUpdate,
    DatasetDetail,
    SampleInfo,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])


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
