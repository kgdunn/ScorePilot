# Developing ScorePilot locally (Linux, from scratch)

This guide assumes **no prior experience** with the tools. Follow it top to bottom
and you will have ScorePilot building, running, and testing on your machine. If you
just want the short version: install the prerequisites, then run
`make setupenv` followed by `make debug`.

---

## 1. What you are about to install (and why)

ScorePilot has a Python backend and a JavaScript-built frontend. You need:

| Tool | What it is | Why |
| ---- | ---------- | --- |
| **git** | Version-control client | To download (clone) the code. |
| **make** | A task runner | Provides the `make setupenv` / `make debug` shortcuts. |
| **curl** | A downloader | Used to install `uv`. |
| **uv** | A fast Python package/runtime manager (by Astral) | Installs the right Python (3.12) and all Python libraries into a project-local virtual environment. You do **not** need to install Python yourself. |
| **Node.js + npm** | JavaScript runtime + package manager | Used **only at build time** to compile the web UI. It is *not* needed to run the shipped app. |

You will not install Python directly - `uv` manages it for you.

---

## 2. Install the prerequisites

### Ubuntu / Debian (most common)

Open a terminal and run:

```bash
sudo apt-get update
sudo apt-get install -y git make curl build-essential
```

### Fedora / RHEL

```bash
sudo dnf install -y git make curl gcc gcc-c++
```

### Arch

```bash
sudo pacman -S --needed git make curl base-devel
```

(`build-essential` / `gcc` provide a C compiler that some Python or Node packages
need to build.)

---

## 3. Get the code

```bash
# Pick a folder for your projects, e.g. ~/code
mkdir -p ~/code && cd ~/code

# Clone the repository
git clone https://github.com/kgdunn/ScorePilot.git
cd ScorePilot
```

> Working on the feature branch? After cloning:
> `git checkout claude/data-exploration-workspace`

---

## 4. Install Node.js (if you don't have it)

Check first:

```bash
node --version   # want v20 or newer
npm --version
```

If those print versions, skip to step 5. Otherwise install Node **without sudo**
using `nvm` (Node Version Manager):

```bash
# 1. Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash

# 2. Load nvm into your CURRENT shell (or just open a new terminal)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# 3. Install the latest LTS Node
nvm install --lts

# 4. Verify
node --version
npm --version
```

`nvm` adds itself to your `~/.bashrc`, so new terminals will have `node`
automatically.

> You do **not** need to install `uv` by hand - `make setupenv` installs it for you
> if it is missing.

---

## 5. Bootstrap everything: `make setupenv`

From the repository root:

```bash
make setupenv
```

This will:

1. Install `uv` if it isn't already present (into `~/.local/bin`, no sudo).
2. Run `uv sync`, which downloads **Python 3.12** and every Python dependency into
   a project-local virtual environment at `.venv/`.
3. Run `npm install` in `frontend/` to fetch the frontend build tools.

If it stops and says Node is missing, do step 4 above and re-run `make setupenv`.

> **If the terminal can't find `uv` right after install:** open a new terminal (or
> run `source ~/.bashrc`) so your `PATH` picks up `~/.local/bin`, then re-run.

---

## 6. Build and run: `make debug`

```bash
make debug
```

This compiles the web UI into the Python package and starts the server. When it
prints that it is running, open your browser at:

```
http://127.0.0.1:8000
```

- The app UI is at `/`.
- The interactive API documentation (Swagger) is at
  **http://127.0.0.1:8000/api/docs** - a great way to try endpoints by hand.

Press **Ctrl-C** in the terminal to stop the server.

Want a different port? `make debug PORT=9000`.

Try it: from the home page, upload a CSV (any table with a header row works), and
you'll land in the data explorer.

---

## 7. The two development modes

### A. Single-server mode (simplest) - `make debug` / `make run`

Builds the UI and serves everything (UI + API) from one URL
(`http://127.0.0.1:8000`). Best when you are working on the **backend** or just
running the app. After changing frontend code you must rebuild
(`make build-frontend`) to see it.

### B. Live-reload mode (best for frontend work) - `make dev`

```bash
make dev
```

Runs **two** servers at once:

- the API (uvicorn) on `http://127.0.0.1:8000` with auto-reload, and
- the Vite dev server on `http://localhost:5173` with instant hot-reload.

Open the **5173** URL. Vite forwards any `/api` request to the backend, so the UI
and API work together while you edit. Both Python and Svelte changes reload
automatically. Ctrl-C stops both.

> Prefer separate terminals? Run `make backend` in one and `make frontend-dev` in
> another - same result.

---

## 8. Everyday commands

| Command | What it does |
| ------- | ------------ |
| `make help` | List all targets. |
| `make setupenv` | One-time bootstrap (uv, Python deps, frontend deps). |
| `make debug` | Build the UI and run the server. |
| `make run` | Run the server (using an already-built UI). |
| `make dev` | Live-reload: backend + Vite together. |
| `make test` | Run the Python test suite (`pytest`). |
| `make lint` | Lint Python (ruff) and type-check the frontend. |
| `make format` | Auto-format and auto-fix Python. |
| `make typecheck` | Type-check Python (pyright). |
| `make check` | Run all gates: lint + format-check + types + tests. |
| `make migrate` | Apply database migrations. |
| `make doctor` | Print tool versions (handy for bug reports). |
| `make clean` | Remove caches, the built UI, and the local DB. |
| `make distclean` | Also remove `.venv` and `node_modules` (full reset). |

Run `make check` before committing - it mirrors what CI will enforce.

---

## 9. Project layout (where things live)

```
src/scorepilot/
  core/          # numerical engine (pure; no web/DB). Profiling, quality, transforms, worksets.
  api/           # FastAPI routers (datasets, exploration, models)
  db/            # SQLAlchemy models + repository
  dataset_store.py  # in-memory dataset store
  app.py         # FastAPI app factory
  main.py        # `scorepilot` CLI entry point
  web/           # built frontend (generated; only a placeholder is committed)
frontend/
  src/lib/grid/  # standalone, reusable data grid (no app-specific code)
  src/lib/components/  # Explorer, Ribbon, VariableInspector, QualityPanel
  src/routes/    # pages: home, /datasets/[id], /playground
tests/           # pytest suite
docs/            # ARCHITECTURE.md, this guide
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for how the pieces fit together.

---

## 10. Debugging tips

- **Server logs** print in the terminal where you ran `make debug`/`make dev`.
  Errors include a traceback pointing at the file and line.
- **Poke the API by hand** at `http://127.0.0.1:8000/api/docs` - expand an
  endpoint, click "Try it out", and send a request.
- **Reset the database** (it's a local SQLite file): `rm scorepilot.db` or
  `make clean`, then restart. A fresh DB is created automatically on startup.
- **Change the port** if 8000 is busy: `make debug PORT=9001`.
- **Python breakpoints:** add `breakpoint()` in any backend `.py` file and run
  `make backend`; execution will drop into the `pdb` debugger in the terminal when
  that line is hit (`n` = next, `c` = continue, `p name` = print).

### VS Code (optional but recommended)

1. Install the extensions: **Python**, **Pylance**, **Ruff**, and **Svelte for VS
   Code**.
2. Select the interpreter: Command Palette -> "Python: Select Interpreter" ->
   choose `./.venv/bin/python`.
3. To debug the backend with breakpoints, create `.vscode/launch.json`:

   ```json
   {
     "version": "0.2.0",
     "configurations": [
       {
         "name": "ScorePilot API",
         "type": "debugpy",
         "request": "launch",
         "module": "uvicorn",
         "args": ["scorepilot.app:create_app", "--factory", "--reload", "--port", "8000"],
         "justMyCode": false
       }
     ]
   }
   ```

   Press F5, set breakpoints in `src/scorepilot/...`, and hit an endpoint.

---

## 11. Troubleshooting

| Symptom | Fix |
| ------- | --- |
| `make: command not found` | Install make (step 2). |
| `uv: command not found` after install | Open a new terminal or `source ~/.bashrc` (adds `~/.local/bin` to PATH), then retry. |
| `make setupenv` says Node is missing | Do step 4 (nvm), open a new terminal, re-run. |
| `Address already in use` on start | Another process holds the port. Use `make debug PORT=9001`, or find it: `lsof -i :8000`. |
| Frontend changes don't show with `make run` | `make run` serves the *built* UI. Rebuild (`make build-frontend`) or use `make dev` for live reload. |
| `npm install` errors about permissions | Don't use sudo with npm. If you installed Node via apt with issues, prefer nvm (step 4). |
| Tests/types fail after pulling new code | Dependencies changed: run `make sync` (Python) and `make frontend-install` (frontend). |
| Everything is weird; start clean | `make distclean && make setupenv`. |

Still stuck? Run `make doctor` and include its output when asking for help.
