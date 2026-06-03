"""FastAPI application factory.

The packaged app is a single process: the API is served under ``/api`` and the
built static frontend at ``/``. A small ``StaticFiles`` subclass falls back to
``index.html`` so client-side (SPA) routes resolve.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Scope

from scorepilot.api import datasets, exploration, models
from scorepilot.config import Settings, get_settings
from scorepilot.dataset_store import DatasetStore
from scorepilot.db import Base, make_engine, make_session_factory

WEB_DIR = Path(__file__).resolve().parent / "web"


class SpaStaticFiles(StaticFiles):
    """Static files that fall back to ``index.html`` on a 404.

    This lets the single-page app own client-side routing while non-existent
    asset paths still return a real 404.
    """

    async def get_response(self, path: str, scope: Scope):  # noqa: ANN201
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application.

    Parameters
    ----------
    settings
        Optional settings override (used by tests). Defaults to the cached
        environment-derived settings.
    """
    settings = settings or get_settings()

    engine = make_engine(settings.database_url)
    # Convenience for local/dev use: ensure tables exist. Production schema
    # changes are managed with Alembic.
    Base.metadata.create_all(engine)

    app = FastAPI(
        title="ScorePilot",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.dataset_store = DatasetStore()

    @app.get("/api/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(datasets.router, prefix="/api")
    app.include_router(exploration.router, prefix="/api")
    app.include_router(models.router, prefix="/api")

    # Mount the static SPA last so it never shadows the API routes above.
    app.mount("/", SpaStaticFiles(directory=WEB_DIR, html=True), name="web")

    return app
