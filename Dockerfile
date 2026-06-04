# syntax=docker/dockerfile:1

# Python-only runtime image. The Svelte frontend is built BEFORE this image (by
# CI, or locally via `make build-frontend`) into src/scorepilot/web, and is then
# baked into the wheel here. Keeping Node out of the image makes the build small,
# fast, and reproducible.
FROM python:3.12-slim AS runtime

# uv provides the Python toolchain and dependency management.
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

RUN uv sync --frozen --no-dev

EXPOSE 8000

# Apply migrations, then serve. SCOREPILOT_DATABASE_URL selects SQLite or Postgres.
CMD ["sh", "-c", "uv run --no-sync alembic upgrade head && exec uv run --no-sync scorepilot --host 0.0.0.0 --port 8000 --no-browser"]
