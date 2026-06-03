"""Dataset upload endpoint and the in-memory dataset store.

For this skeleton, uploaded datasets live in process memory keyed by a generated
id; the fit endpoint references that id. Persisting datasets is a later concern -
the store can be swapped for a DB/object-storage backing without changing the
endpoints.
"""

from __future__ import annotations

import io
from typing import Annotated
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from scorepilot.api.deps import DatasetStoreDep
from scorepilot.schemas import DatasetSummary

router = APIRouter(prefix="/datasets", tags=["datasets"])


class DatasetStore:
    """A simple in-memory registry of uploaded DataFrames."""

    def __init__(self) -> None:
        self._frames: dict[str, pd.DataFrame] = {}

    def add(self, frame: pd.DataFrame) -> str:
        dataset_id = uuid4().hex
        self._frames[dataset_id] = frame
        return dataset_id

    def get(self, dataset_id: str) -> pd.DataFrame | None:
        return self._frames.get(dataset_id)


@router.post("", response_model=DatasetSummary, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    store: DatasetStoreDep,
    file: Annotated[UploadFile, File(description="CSV with sample ids in column 1")],
) -> DatasetSummary:
    """Upload a CSV dataset.

    The first column is treated as the sample (observation) identifier; the
    remaining columns must be numeric variables.
    """
    raw = await file.read()
    try:
        frame = pd.read_csv(io.BytesIO(raw), index_col=0)
    except (ValueError, pd.errors.ParserError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse CSV: {exc}",
        ) from exc

    numeric = frame.select_dtypes("number")
    if numeric.shape[1] == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No numeric variable columns found after the index column.",
        )

    dataset_id = store.add(numeric)
    return DatasetSummary(
        dataset_id=dataset_id,
        n_rows=int(numeric.shape[0]),
        n_columns=int(numeric.shape[1]),
        columns=[str(c) for c in numeric.columns],
    )
