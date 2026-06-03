# ScorePilot architecture

This document describes how ScorePilot is put together and the principles that
keep it maintainable. It complements the per-module docstrings and `CLAUDE.md`.

## Overview

ScorePilot is a single pip/uvx-installable application for PCA/PLS model analysis
in chemometrics. It runs as **one process**: a FastAPI backend serves the JSON API
under `/api` and the pre-built single-page frontend at `/`. No Node is required at
runtime.

```
 Browser (SvelteKit SPA, ECharts)
        |  HTTP /api
        v
 FastAPI app  ──>  in-memory dataset store
   (api/)            (dataset_store.py)
        |
        v
   core/  ── pure numpy/pandas/scipy, wraps process-improve
        |
        v
   db/   ── SQLAlchemy 2.0 ORM + repository (SQLite / Postgres)
```

## Layers and the load-bearing boundary

- **`core/`** is the numerical engine: pure functions over numpy arrays and pandas
  DataFrames. It wraps the [`process-improve`](https://github.com/kgdunn/process_improve)
  library for the heavy chemometrics (PCA/PLS, T², SPE, VIP, limits) and adds only
  what is missing upstream (column-type inference, histograms, transforms). **It
  imports no FastAPI, SQLAlchemy, or other web/DB code.** This boundary is what lets
  the numerics be tested and reasoned about in isolation, and is enforced by review
  and by the dependency direction (nothing in `core/` imports the layers below).

- **`db/`** is SQLAlchemy 2.0 (typed `Mapped[]`) plus a repository interface. The
  same code runs on SQLite locally and Postgres in production. Model lineage is a
  self-referencing `parent_id` traversed with a recursive CTE - not a graph
  database - so it is portable across both engines.

- **`api/`** is a thin FastAPI layer translating HTTP to `core`/`db`/store. Routers
  hold no numerics; they validate input (Pydantic v2 schemas), call into the lower
  layers, and shape responses.

- **`frontend/`** is a SvelteKit SPA (Svelte 5 runes) using ECharts for all plots.
  It is built (`@sveltejs/adapter-static`, SPA mode) into `src/scorepilot/web` and
  force-included into the wheel.

## The dataset / preprocessing-spec split (load-bearing)

The most important domain decision is that a **dataset is immutable** and **all
modelling choices live in a per-variant preprocessing recipe**.

- A `Dataset` (`dataset_store.py`) holds the raw table plus intrinsic metadata:
  each column's **data type** (Quantitative / Qualitative / Date-Time) and optional
  **identifier role** (Primary / Secondary / Class), and a data-quality view. It is
  never transformed in place.

- A `PreprocessingSpec` (`core/workset.py`) captures what defines a *model variant*:
  which columns are **X**/**Y**, which rows/columns are **excluded**, and the
  per-variable **transform** and **scaling**. `apply_spec(df, spec)` produces the
  model-ready X (and Y) matrices.

This matters because the same dataset is analysed many ways over time: model 1 may
apply no transform, while models 2/3/4 try different transforms of different
variables. Each variant carries its own spec, so they never fight over a single
mutable dataset. A spec serializes to plain JSON and round-trips through the
existing `Model.preprocessing` column; variants are linked by `Model.parent_id`,
giving a lineage of recipes over one dataset.

During data exploration the spec is a *draft* held in the browser and used only for
previews; nothing is fitted or persisted until the modelling stage.

## Persistence model

- `Model`: queryable metadata in real columns / JSON (`kind`, `n_components`,
  `preprocessing`, `excluded_samples`), with fitted arrays stored as a compressed
  `npz` blob in `params`. If artifacts grow, the blob can be swapped for an
  object-storage path behind the same repository method.
- Datasets are currently **in-memory** (`DatasetStore`). The store exposes the
  interface a future `Dataset` table / repository would implement, so moving to the
  database does not change callers.

## The reusable data grid

`frontend/src/lib/grid/` is a **standalone, dependency-free, domain-agnostic**
virtualized grid. It knows nothing about roles, types, or quality: the caller
supplies columns, a row count, and a cell accessor, and injects all styling and
header/cell content through class callbacks and snippets. ScorePilot's
`Explorer.svelte` composes it and layers the domain behaviour on top. The folder
has no ScorePilot imports and can be lifted into another app as-is.

## Request flow example: exploring a dataset

1. `POST /api/datasets` parses a CSV/Excel file (`load_table`), keeps every column,
   infers each column's type, and stores a `Dataset`.
2. The Explorer fetches `GET /api/datasets/{id}` (metadata),
   `GET /api/datasets/{id}/grid` (windowed cells, raw or autoscaled), and
   `GET /api/datasets/{id}/quality`.
3. Selecting a column fetches `GET /api/datasets/{id}/variables/{column}` for the
   inspector; a transform query parameter drives a non-destructive preview.
4. Role/type/identifier edits `PATCH` the dataset; X/Y, exclusions, and transforms
   accumulate in the client-held draft spec, ready to become a model variant later.

## Testing strategy

- `core/` has unit tests over synthetic and real-shaped data (type inference,
  summaries, quality flags, transforms, `apply_spec`).
- `api/` has FastAPI `TestClient` tests for import, exploration, and fitting.
- Broader unit-test coverage, frontend component tests, and Playwright end-to-end
  tests in CI are tracked as roadmap issues.

## Constraints / non-goals

- No graph database (lineage is a recursive CTE).
- No Node at runtime (build-time only).
- Static SPA frontend (`ssr = false`, `fallback: index.html`).
- The optional in-app assistant is pluggable and never required for analysis.
