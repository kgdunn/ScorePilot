"""Repository interfaces over the ORM.

``ModelRepository`` and ``DatasetRepository`` protocols abstract persistence so
the rest of the app never touches the ORM session directly. The SQLAlchemy
implementations work unchanged on SQLite and Postgres.
"""

from __future__ import annotations

from typing import Protocol
from uuid import uuid4

import pandas as pd
from sqlalchemy import literal, select
from sqlalchemy.orm import Session, aliased

from scorepilot.dataset_store import (
    Dataset,
    column_from_dict,
    column_to_dict,
    deserialize_frame,
    prepare_dataset,
    serialize_frame,
)
from scorepilot.db.models import DatasetRecord, Model


class ModelRepository(Protocol):
    """Persistence operations for fitted models."""

    def add(self, model: Model) -> Model:
        """Persist a new model and return it (with its assigned ``id``)."""
        ...

    def update(self, model: Model) -> Model:
        """Persist changes to an already-tracked model and return it."""
        ...

    def get(self, model_id: int) -> Model | None:
        """Return the model with ``model_id``, or ``None`` if absent."""
        ...

    def list(self) -> list[Model]:
        """Return all models, oldest first."""
        ...

    def lineage(self, model_id: int) -> list[Model]:
        """Return the ancestry chain of ``model_id``, root first."""
        ...


class SqlModelRepository:
    """SQLAlchemy-backed :class:`ModelRepository`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, model: Model) -> Model:
        self._session.add(model)
        self._session.flush()
        return model

    def update(self, model: Model) -> Model:
        # ``model`` is already attached to the session; flush the mutation so it
        # is persisted when the request's transaction commits.
        self._session.flush()
        return model

    def get(self, model_id: int) -> Model | None:
        return self._session.get(Model, model_id)

    def list(self) -> list[Model]:
        return list(self._session.scalars(select(Model).order_by(Model.id)))

    def lineage(self, model_id: int) -> list[Model]:
        """Walk ``parent_id`` from ``model_id`` up to the root via a recursive CTE.

        The same query runs on SQLite and Postgres. The returned list is ordered
        root first, ending with the model itself.
        """
        anchor = (
            select(
                Model.id.label("id"),
                Model.parent_id.label("parent_id"),
                literal(0).label("depth"),
            )
            .where(Model.id == model_id)
            .cte("lineage", recursive=True)
        )
        parent = aliased(Model)
        recursive = select(
            parent.id,
            parent.parent_id,
            (anchor.c.depth + 1).label("depth"),
        ).join(anchor, parent.id == anchor.c.parent_id)
        lineage = anchor.union_all(recursive)

        ordered_ids = list(
            self._session.scalars(select(lineage.c.id).order_by(lineage.c.depth.desc()))
        )
        if not ordered_ids:
            return []
        by_id = {
            m.id: m for m in self._session.scalars(select(Model).where(Model.id.in_(ordered_ids)))
        }
        return [by_id[i] for i in ordered_ids]


class DatasetRepository(Protocol):
    """Persistence operations for imported datasets.

    Mirrors the operations callers previously used on the in-memory store, so the
    API routers are unchanged apart from saving column-metadata edits.
    """

    def add(
        self,
        name: str,
        frame: pd.DataFrame,
        *,
        source: str = "csv",
        sheets: list[str] | None = None,
        sheet: str | None = None,
    ) -> Dataset:
        """Persist a new dataset from an imported frame and return it."""
        ...

    def get(self, dataset_id: str) -> Dataset | None:
        """Return the dataset with ``dataset_id``, or ``None`` if absent."""
        ...

    def list(self) -> list[Dataset]:
        """Return all datasets, oldest first."""
        ...

    def save(self, dataset: Dataset) -> Dataset:
        """Persist edits to a dataset's column metadata (name, types, roles)."""
        ...


def _to_dataset(
    record: DatasetRecord,
    frame: pd.DataFrame | None = None,
    columns: list | None = None,
) -> Dataset:
    """Build a working :class:`Dataset` from a stored record.

    ``frame``/``columns`` may be passed in to avoid re-deserializing right after a
    write.
    """
    return Dataset(
        id=record.id,
        name=record.name,
        raw=frame if frame is not None else deserialize_frame(record.data),
        columns=columns if columns is not None else [column_from_dict(c) for c in record.columns],
        source=record.source,
        sheet=record.sheet,
        sheets=list(record.sheets),
    )


class SqlDatasetRepository:
    """SQLAlchemy-backed :class:`DatasetRepository`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        name: str,
        frame: pd.DataFrame,
        *,
        source: str = "csv",
        sheets: list[str] | None = None,
        sheet: str | None = None,
    ) -> Dataset:
        # prepare_dataset may add a synthetic identifier column, so persist the
        # frame it returns (not the original).
        prepared, columns = prepare_dataset(frame)
        record = DatasetRecord(
            id=uuid4().hex,
            name=name,
            source=source,
            sheet=sheet,
            sheets=list(sheets or []),
            columns=[column_to_dict(c) for c in columns],
            data=serialize_frame(prepared),
        )
        self._session.add(record)
        self._session.flush()
        return _to_dataset(record, frame=prepared, columns=columns)

    def get(self, dataset_id: str) -> Dataset | None:
        record = self._session.get(DatasetRecord, dataset_id)
        return None if record is None else _to_dataset(record)

    def list(self) -> list[Dataset]:
        records = self._session.scalars(select(DatasetRecord).order_by(DatasetRecord.created_at))
        return [_to_dataset(r) for r in records]

    def save(self, dataset: Dataset) -> Dataset:
        record = self._session.get(DatasetRecord, dataset.id)
        if record is None:
            msg = f"Unknown dataset_id: {dataset.id}"
            raise KeyError(msg)
        # The raw table is immutable; only the name and column metadata can change.
        record.name = dataset.name
        record.columns = [column_to_dict(c) for c in dataset.columns]
        self._session.flush()
        return dataset
