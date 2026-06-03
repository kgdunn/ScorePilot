# ScorePilot

A web-based tool for **PCA/PLS model analysis** in chemometrics / multivariate
data analysis. You build up model *variants* by changing preprocessing,
including or excluding samples, and testing models on new data. The central
collection of those variants is the **Hangar**; each model carries a **Logbook**
entry recording its preprocessing, excluded samples, and validation history.

The numerical core is provided by the
[`process-improve`](https://github.com/kgdunn/process_improve) library (PCA, PLS,
Hotelling's T², SPE/DModX, contributions, VIP, cross-validated Q²). ScorePilot
wraps it behind a FastAPI backend and a SvelteKit + ECharts frontend, shipped as
a single pip/uvx-installable package.

## Architecture at a glance

- **`core/`** - pure numerical functions over arrays/DataFrames; wraps
  `process-improve`. No web/DB imports.
- **`db/`** - SQLAlchemy 2.0 ORM + repository interface (SQLite locally,
  Postgres in production). Model lineage is a self-referencing `parent_id`
  traversed with a recursive CTE.
- **`api/`** - thin FastAPI routers translating HTTP to `core`/`db`.
- **`frontend/`** - SvelteKit (Svelte 5 runes) + Vite + ECharts, built into
  `src/scorepilot/web` and served as static files.

The packaged app is **one process**: FastAPI serves `/api` and the built static
frontend at `/`. No Node is required at runtime.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for a fuller description,
including the dataset / preprocessing-spec split and the reusable data grid.

## What you can do today

- **Import** a CSV or Excel file; every column is kept and its data type
  (quantitative / qualitative / date-time) is inferred.
- **Explore** the data in a virtualized grid: assign identifier roles
  (primary / secondary / class), choose X / Y variables, and exclude observations
  (rows) or variables (columns).
- **Check data quality**: duplicate primary identifiers, invalid values in
  quantitative columns, and missing data.
- **Inspect** any variable: summary statistics, a frequency histogram, a sequence
  plot, and a non-destructive transform preview, plus a raw vs autoscaled view.

The dataset stays immutable; transforms, scaling, X/Y, and exclusions accumulate in
a preprocessing recipe that will drive model variants in the next stage. A small
PCA scores demo lives at `/playground`.

## Run it (local)

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                 # create the environment
uv run scorepilot       # boot uvicorn and open the browser
```

`uv run scorepilot` serves the bundled frontend (a placeholder until you build
the real one - see below) and the API at `http://127.0.0.1:8000`. API docs are
at `http://127.0.0.1:8000/api/docs`.

Useful flags:

```bash
uv run scorepilot --host 0.0.0.0 --port 8080 --no-browser
```

## Develop

Run the backend and the Vite dev server side by side. The Vite server proxies
`/api` to uvicorn, so the frontend gets hot-reload while talking to the real API.

```bash
# terminal A - backend (auto-reload)
uv run uvicorn scorepilot.app:create_app --factory --reload

# terminal B - frontend dev server
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite (default `http://localhost:5173`).

### Build the frontend into the package

The compiled bundle is **not** committed; it is built into `src/scorepilot/web`
and force-included into the wheel at release time:

```bash
cd frontend
npm run build           # outputs to ../src/scorepilot/web
```

After building, `uv run scorepilot` serves the real UI.

## Quality gates

```bash
uv run ruff check .     # lint
uv run ruff format .    # format
uv run pyright          # type check
uv run pytest           # tests
```

Install the git hooks once with `uv run pre-commit install`.

## Database / migrations

SQLite is used locally (default `sqlite:///./scorepilot.db`); set
`SCOREPILOT_DATABASE_URL` to point at Postgres in production.

```bash
uv run alembic upgrade head                         # apply migrations
uv run alembic revision --autogenerate -m "message" # create a new migration
```

## License

MIT. See [LICENSE](LICENSE).
