"""Repository interface over the ORM.

A single ``ModelRepository`` protocol abstracts persistence so the rest of the
app never touches the ORM session directly. The SQLAlchemy implementation works
unchanged on SQLite and Postgres.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import literal, select
from sqlalchemy.orm import Session, aliased

from scorepilot.db.models import Model


class ModelRepository(Protocol):
    """Persistence operations for fitted models."""

    def add(self, model: Model) -> Model:
        """Persist a new model and return it (with its assigned ``id``)."""
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
