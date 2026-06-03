"""FastAPI dependencies wiring requests to the dataset store and repository."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from scorepilot.dataset_store import DatasetStore
from scorepilot.db import SqlModelRepository, session_scope


def get_dataset_store(request: Request) -> DatasetStore:
    """Return the process-wide in-memory dataset store."""
    return request.app.state.dataset_store


def get_session(request: Request) -> Iterator[Session]:
    """Yield a transactional session, committed when the request succeeds."""
    with session_scope(request.app.state.session_factory) as session:
        yield session


def get_repository(
    session: Annotated[Session, Depends(get_session)],
) -> SqlModelRepository:
    """Return a repository bound to the request's session."""
    return SqlModelRepository(session)


DatasetStoreDep = Annotated[DatasetStore, Depends(get_dataset_store)]
RepositoryDep = Annotated[SqlModelRepository, Depends(get_repository)]
