"""FastAPI application factory.

The packaged app is a single process: the API is served under ``/api`` and the
built static frontend at ``/``. A small ``StaticFiles`` subclass falls back to
``index.html`` so client-side (SPA) routes resolve.
"""

from __future__ import annotations

import base64
import binascii
import secrets
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Scope

from scorepilot import __version__
from scorepilot.api import datasets, exploration, models
from scorepilot.config import Settings, get_settings
from scorepilot.db import Base, make_engine, make_session_factory

WEB_DIR = Path(__file__).resolve().parent / "web"

# Exempt from the auth gate so reverse-proxy / container health checks keep working.
_AUTH_EXEMPT_PATHS = frozenset({"/api/health"})


def _basic_auth_ok(header: str | None, username: str, password: str) -> bool:
    """Constant-time check of an ``Authorization: Basic`` header."""
    if not header or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:], validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    user, sep, supplied = decoded.partition(":")
    if not sep:
        return False
    # Compare both halves with compare_digest to avoid leaking length/contents by timing.
    user_ok = secrets.compare_digest(user, username)
    pw_ok = secrets.compare_digest(supplied, password)
    return user_ok and pw_ok


class SpaStaticFiles(StaticFiles):
    """Static files that fall back to ``index.html`` on a 404.

    This lets the single-page app own client-side routing while non-existent
    asset paths still return a real 404.

    Cache policy avoids the stale-SPA trap (notably on iOS Safari): the HTML
    shell is served ``no-cache`` so a new deploy is picked up immediately, while
    SvelteKit's content-hashed assets under ``_app/immutable/`` are cached
    forever. Without this, a cached shell can keep pointing at hashed chunks that
    a redeploy has already removed, and the app loads only partially.
    """

    async def get_response(self, path: str, scope: Scope):  # noqa: ANN201
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            response = await super().get_response("index.html", scope)
        if path.startswith("_app/immutable/"):
            response.headers["cache-control"] = "public, max-age=31536000, immutable"
        elif response.headers.get("content-type", "").startswith("text/html"):
            response.headers["cache-control"] = "no-cache"
        return response


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
        version=__version__,
        # Interactive docs are opt-out: deployers can shrink the public surface.
        docs_url="/api/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.docs_enabled else None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)

    # Optional HTTP Basic auth gate. Inactive unless a password is configured, so a
    # local launch needs no login; on a public deploy it covers the whole app (API,
    # docs, and the static SPA) and the browser handles the credential prompt.
    if settings.auth_password:
        password = settings.auth_password
        username = settings.auth_username

        @app.middleware("http")
        async def require_basic_auth(request: Request, call_next):  # noqa: ANN001, ANN202
            if request.url.path in _AUTH_EXEMPT_PATHS:
                return await call_next(request)
            if not _basic_auth_ok(request.headers.get("Authorization"), username, password):
                return Response(
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="ScorePilot"'},
                )
            return await call_next(request)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/version", tags=["meta"])
    def version() -> dict[str, str]:
        """The running app version, surfaced in the web UI to confirm the deploy."""
        return {"version": __version__}

    app.include_router(datasets.router, prefix="/api")
    app.include_router(exploration.router, prefix="/api")
    app.include_router(models.router, prefix="/api")

    # Mount the static SPA last so it never shadows the API routes above.
    app.mount("/", SpaStaticFiles(directory=WEB_DIR, html=True), name="web")

    return app
