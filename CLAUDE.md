# CLAUDE.md

Project guidance for Claude Code. Read this at the start of every session.

## What ScorePilot is

A web-based tool for PCA/PLS model analysis in chemometrics / multivariate data
analysis, aimed at a scientific (English-speaking) audience. Users accumulate
model *variants* by changing preprocessing, including/excluding samples, and
testing models on new data.

### Domain glossary

- **Hangar** — the central collection of all model variants a user has built.
- **Logbook** — a model's provenance record: preprocessing, excluded samples,
  validation history.
- **T^2-D2** — the optional in-app assistant (LLM). Off by default; the core must
  work fully without it.
- Standard chemometrics terms keep their established names — scores (T),
  loadings (P), weights (W), Hotelling's T², SPE/DModX, contributions, VIP,
  R²X / R²Y, Q². Do not invent new names for these.

## Architecture

- **`core/`** — the numerical engine (numpy / scipy / scikit-learn): PCA, PLS,
  T², SPE/DModX, contributions, VIP, cross-validated Q². Pure functions over
  arrays / DataFrames. **No FastAPI, SQLAlchemy, or any web/DB imports here.**
  This boundary is load-bearing — keep it clean and independently testable.
- **`db/`** — SQLAlchemy 2.0 ORM + a repository interface. SQLite locally,
  Postgres in production, same interface for both.
- **`api/`** — FastAPI routers. Thin layer translating HTTP ↔ core/db.
- **`frontend/`** — SvelteKit (Svelte 5 runes) + Vite, ECharts for all plots.
  Builds into `src/scorepilot/web`. `frontend/src/lib/grid/` is a standalone,
  dependency-free, domain-agnostic data grid intended to be reusable in other
  apps — keep ScorePilot concepts (roles, quality) out of it and layer them on
  via snippets/props in `Explorer.svelte`.
- The packaged app is **one process**: FastAPI serves `/api` and the built
  static frontend at `/`.

## Constraints / non-goals (do not reintroduce)

- **No graph database.** Model lineage is a self-referencing `parent_id`
  traversed with a recursive CTE — supported identically by SQLite and Postgres.
- **No Node at runtime.** Node is a build-time tool only. `uvx scorepilot` must
  run with Python alone.
- **Static frontend** (`@sveltejs/adapter-static`, SPA mode, `ssr = false`).
  No SvelteKit Node server.
- **The agent is optional and pluggable** (bring-your-own key / local
  Ollama). Analysis never depends on it.

## Commands

Python (uv):

- Install: `uv sync`
- Run app: `uv run scorepilot` (boots uvicorn, opens the browser)
- Tests: `uv run pytest`
- Lint / format: `uv run ruff check .` / `uv run ruff format .`
- Types: `uv run pyright`
- Migrations: `uv run alembic revision --autogenerate -m "..."` then
  `uv run alembic upgrade head`

Frontend (run inside `frontend/`):

- Dev: `npm run dev` (Vite proxies `/api` → uvicorn)
- Build: `npm run build` (output copied into `src/scorepilot/web`)

During development, run uvicorn and the Vite dev server together.

## Conventions

- Python 3.12+, full type hints, SQLAlchemy 2.0 typed `Mapped[]` style.
- Clean, concise, idiomatic code; prefer pure functions in `core/`.
- Pydantic v2 for API schemas and settings (`pydantic-settings`).
- Svelte 5 runes; keep ECharts setup in a small reusable `lib` module rather
  than inline in pages.
- Small, focused commits. Run ruff + type check + tests before committing.
- Pre-commit hooks enforce lint / format / type checks.

## Data model notes

- `Model`: `id`, `parent_id` (self-FK, `NULL` = root), `kind` (`"PCA"` /
  `"PLS"`), `n_components`, `preprocessing` (JSON/JSONB), `excluded_samples`
  (JSON), `params` (compressed `npz` blob — P, W, means, scales…), `created_at`.
- Keep queryable metadata in real columns / JSON; store fitted arrays as a
  `np.savez_compressed` blob. If artifacts grow, swap the blob for an
  object-storage path behind the same repository method — nothing upstream
  should change.
- **Datasets are immutable; preprocessing is a per-variant recipe.** A dataset
  holds only intrinsic metadata (column data types, identifier roles, quality).
  X/Y selection, row/column exclusions, transforms, and scaling live in a
  `PreprocessingSpec` (`core/workset.py`), applied with `apply_spec(df, spec)`.
  One dataset has many specs (one per model variant); a spec serializes into
  `Model.preprocessing` and variants form the `parent_id` lineage. Never bake
  transforms onto the dataset. Datasets are currently in-memory
  (`dataset_store.py`) behind an interface a DB table can later implement.

## Working style

- For non-trivial changes, propose a short plan and the affected files before
  editing in bulk.
- Flag assumptions explicitly.
- Keep this file up to date when conventions or commands change.
