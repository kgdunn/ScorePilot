"""FastAPI dependencies wiring requests to the dataset and model repositories."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from scorepilot.config import Settings
from scorepilot.db import SqlDatasetRepository, SqlModelRepository, session_scope


def get_settings_dep(request: Request) -> Settings:
    """Return the settings the app was built with (per-app, not the global cache)."""
    return request.app.state.settings


def get_session(request: Request) -> Iterator[Session]:
    """Yield a transactional session, committed when the request succeeds.

    FastAPI caches this dependency per request, so the dataset and model
    repositories below share one session and commit atomically.
    """
    with session_scope(request.app.state.session_factory) as session:
        yield session


def get_repository(
    session: Annotated[Session, Depends(get_session)],
) -> SqlModelRepository:
    """Return a model repository bound to the request's session."""
    return SqlModelRepository(session)


def get_dataset_store(
    session: Annotated[Session, Depends(get_session)],
) -> SqlDatasetRepository:
    """Return a dataset repository bound to the request's session."""
    return SqlDatasetRepository(session)


DatasetStoreDep = Annotated[SqlDatasetRepository, Depends(get_dataset_store)]
RepositoryDep = Annotated[SqlModelRepository, Depends(get_repository)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
