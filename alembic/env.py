"""Alembic migration environment for ScorePilot.

The database URL and target metadata come from the application itself, so
migrations always match the ORM and the configured ``SCOREPILOT_DATABASE_URL``.

The URL is used directly (never written into the Alembic/ConfigParser ini), so
passwords containing characters like ``%`` or ``@`` do not break migrations.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from scorepilot.config import get_settings
from scorepilot.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (emit SQL)."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = create_engine(
        get_settings().database_url, poolclass=pool.NullPool, future=True
    )
    with connectable.connect() as connection:
        # batch mode keeps ALTER operations working on SQLite.
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
