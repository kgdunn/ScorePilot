"""Application settings, loaded from the environment via pydantic-settings.

All settings are read from ``SCOREPILOT_*`` environment variables (or a local
``.env`` file). SQLite is the default store; point ``SCOREPILOT_DATABASE_URL`` at
Postgres in production.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for ScorePilot.

    Attributes
    ----------
    database_url
        SQLAlchemy database URL. Defaults to a local SQLite file.
    host, port
        Address uvicorn binds to when launched via the ``scorepilot`` CLI.
    open_browser
        Whether the CLI opens a browser window on startup.
    agent_enabled, agent_api_key, agent_base_url, agent_model_name
        Optional T^2-D2 assistant configuration. The agent is off by default and
        the analysis features never depend on it.
    """

    model_config = SettingsConfigDict(
        env_prefix="SCOREPILOT_",
        env_file=".env",
        extra="ignore",
        protected_namespaces=(),
    )

    database_url: str = "sqlite:///./scorepilot.db"
    host: str = "127.0.0.1"
    port: int = 8000
    open_browser: bool = True

    agent_enabled: bool = False
    agent_api_key: str | None = None
    agent_base_url: str | None = None
    agent_model_name: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
