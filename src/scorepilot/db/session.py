"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from scorepilot.config import get_settings


def make_engine(database_url: str | None = None) -> Engine:
    """Create an engine for ``database_url`` (defaults to the configured URL).

    SQLite needs ``check_same_thread=False`` so a connection can be shared across
    the threads uvicorn uses; other backends get no special connect args.
    """
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a configured ``sessionmaker`` bound to ``engine``."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a transactional session scope, committing or rolling back."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
