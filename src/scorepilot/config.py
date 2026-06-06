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

    # --- Hardening knobs (all opt-in; defaults keep the local launch frictionless) ---
    # HTTP Basic auth gate. Disabled while ``auth_password`` is unset, so a local
    # ``uvx scorepilot`` needs no login; set a password to require auth on a public
    # deploy (the browser prompts natively and the SPA inherits the credentials).
    auth_username: str = "scorepilot"
    auth_password: str | None = None

    # Serve the interactive API docs (``/api/docs`` + OpenAPI). Leave on for local
    # use; deployers can turn it off to shrink the public surface.
    docs_enabled: bool = True

    # Resource caps that bound memory regardless of who is calling. ``max_upload_mb``
    # caps a single uploaded/fetched body; ``max_cells`` caps the parsed table so a
    # small but highly compressed file (e.g. an ``.xlsx``) cannot expand without limit.
    max_upload_mb: int = 100
    max_cells: int = 50_000_000


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
