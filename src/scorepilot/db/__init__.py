"""Persistence layer: ORM models, sessions, and the repository interface."""

from scorepilot.db.models import Base, DatasetRecord, Model
from scorepilot.db.repository import (
    DatasetRepository,
    ModelRepository,
    SqlDatasetRepository,
    SqlModelRepository,
)
from scorepilot.db.session import (
    make_engine,
    make_session_factory,
    session_scope,
)

__all__ = [
    "Base",
    "DatasetRecord",
    "DatasetRepository",
    "Model",
    "ModelRepository",
    "SqlDatasetRepository",
    "SqlModelRepository",
    "make_engine",
    "make_session_factory",
    "session_scope",
]
