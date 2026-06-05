"""SQLAlchemy ORM models.

A fitted model is one row in the ``model`` table. Lineage between variants is a
self-referencing ``parent_id`` (NULL for a root), deliberately *not* a graph
database: it is traversed with a recursive CTE that works identically on SQLite
and Postgres.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class DatasetRecord(Base):
    """An imported dataset, persisted so it survives a restart.

    Queryable metadata lives in real columns and JSON (``columns`` holds each
    column's data type and identifier role); the immutable raw table is stored as
    a gzipped-CSV blob in ``data``. If those blobs grow, ``data`` can be swapped
    for an object-storage path behind the same repository method.
    """

    __tablename__ = "dataset"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(20), default="csv")
    sheet: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sheets: Mapped[list] = mapped_column(JSON, default=list)
    columns: Mapped[list] = mapped_column(JSON, default=list)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"DatasetRecord(id={self.id!r}, name={self.name!r})"


class Model(Base):
    """A fitted PCA/PLS model variant.

    Queryable metadata lives in real columns and JSON; the fitted arrays (P, W,
    means, scales, ...) are stored as a compressed ``npz`` blob in ``params``. If
    those artifacts grow, ``params`` can be swapped for an object-storage path
    behind the same repository method without changing anything upstream.
    """

    __tablename__ = "model"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("model.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(8))  # "PCA" or "PLS"
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dataset_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    n_components: Mapped[int]
    preprocessing: Mapped[dict] = mapped_column(JSON, default=dict)
    excluded_samples: Mapped[list] = mapped_column(JSON, default=list)
    params: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    parent: Mapped[Model | None] = relationship(
        "Model", remote_side=[id], back_populates="children"
    )
    children: Mapped[list[Model]] = relationship(
        "Model", back_populates="parent", passive_deletes=True
    )

    def __repr__(self) -> str:
        return (
            f"Model(id={self.id!r}, parent_id={self.parent_id!r}, "
            f"kind={self.kind!r}, n_components={self.n_components!r})"
        )
