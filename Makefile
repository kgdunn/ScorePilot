# ScorePilot developer Makefile.
#
# Newcomers: run `make setupenv` once, then `make debug` to build and launch the
# app. See `docs/DEVELOPMENT.md` for a from-scratch walkthrough. Run `make help`
# to list every target.

# Use bash, fail fast, and run each recipe in a single shell.
SHELL := /bin/bash
.SHELLFLAGS := -e -u -c
.ONESHELL:

# Ensure tools installed into the user's home (uv, nvm-managed node) are found.
export PATH := $(HOME)/.local/bin:$(PATH)

# Host/port the dev server binds to (override: `make debug PORT=9000`).
HOST ?= 127.0.0.1
PORT ?= 8000

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help.
	@echo "ScorePilot - common tasks"
	@echo
	@grep -E '^[a-zA-Z][a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "First time?  run:  make setupenv   then:  make debug"

# ---------------------------------------------------------------------------
# Bootstrapping
# ---------------------------------------------------------------------------

.PHONY: setupenv
setupenv: _ensure-uv _ensure-node ## Bootstrap everything (uv, Python deps, frontend deps).
	@echo "==> Installing Python toolchain and dependencies with uv"
	uv sync
	@echo "==> Installing frontend dependencies with npm"
	cd frontend && npm install
	@echo
	@echo "Done. Next:  make debug   (build the UI and run the app)"

.PHONY: _ensure-uv
_ensure-uv: ## (internal) Install uv if it is missing.
	if ! command -v uv >/dev/null 2>&1; then
		echo "==> uv not found; installing it (user-space, no sudo)"
		if ! command -v curl >/dev/null 2>&1; then
			echo "ERROR: 'curl' is required to install uv. Install it first:"
			echo "       sudo apt-get update && sudo apt-get install -y curl"
			exit 1
		fi
		curl -LsSf https://astral.sh/uv/install.sh | sh
	fi
	echo "==> uv: $$(uv --version)"

.PHONY: _ensure-node
_ensure-node: ## (internal) Verify Node.js / npm are available.
	if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
		echo "ERROR: Node.js (with npm) was not found."
		echo "       Install Node 20+ and re-run 'make setupenv'."
		echo "       Recommended (no sudo) with nvm:"
		echo "         curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"
		echo "         # then open a new terminal (or 'source ~/.bashrc') and:"
		echo "         nvm install --lts"
		echo "       See docs/DEVELOPMENT.md for details."
		exit 1
	fi
	echo "==> node: $$(node --version), npm: $$(npm --version)"

.PHONY: sync
sync: ## Install/refresh Python dependencies (creates .venv).
	uv sync

.PHONY: frontend-install
frontend-install: ## Install frontend dependencies.
	cd frontend && npm install

# ---------------------------------------------------------------------------
# Build & run
# ---------------------------------------------------------------------------

.PHONY: build-frontend
build-frontend: ## Compile the Svelte UI into src/scorepilot/web.
	cd frontend && npm run build

.PHONY: run
run: ## Run the app (serves the already-built UI) and open the browser.
	uv run scorepilot --host $(HOST) --port $(PORT)

.PHONY: debug
debug: sync build-frontend ## Install deps, compile the UI, and run the server.
	@echo "==> Starting ScorePilot at http://$(HOST):$(PORT)  (Ctrl-C to stop)"
	uv run scorepilot --host $(HOST) --port $(PORT)

.PHONY: backend
backend: ## Run only the API with auto-reload (no browser); pair with 'make frontend-dev'.
	uv run uvicorn scorepilot.app:create_app --factory --reload --host $(HOST) --port $(PORT)

.PHONY: frontend-dev
frontend-dev: ## Run only the Vite dev server (proxies /api to the backend).
	cd frontend && npm run dev

.PHONY: dev
dev: ## Live-reload dev: run backend + Vite together (open the Vite URL it prints).
	@echo "==> Backend on http://$(HOST):$(PORT), Vite dev server starting below."
	@echo "==> Open the http://localhost:5173 URL Vite prints. Ctrl-C stops both."
	trap 'kill 0' EXIT
	uv run uvicorn scorepilot.app:create_app --factory --reload --host $(HOST) --port $(PORT) &
	cd frontend && npm run dev
	wait

# ---------------------------------------------------------------------------
# Quality & database
# ---------------------------------------------------------------------------

.PHONY: test
test: ## Run the Python test suite.
	uv run pytest

.PHONY: lint
lint: ## Lint Python (ruff) and type-check the frontend (svelte-check).
	uv run ruff check .
	cd frontend && npm run check

.PHONY: format
format: ## Auto-format Python with ruff.
	uv run ruff format .
	uv run ruff check --fix .

.PHONY: typecheck
typecheck: ## Type-check Python with pyright.
	uv run pyright

.PHONY: check
check: ## Run all quality gates (lint, types, tests).
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright
	uv run pytest
	cd frontend && npm run check

.PHONY: migrate
migrate: ## Apply database migrations (alembic upgrade head).
	uv run alembic upgrade head

.PHONY: doctor
doctor: ## Print versions of the key tools.
	@echo "uv:     $$(command -v uv >/dev/null 2>&1 && uv --version || echo 'NOT INSTALLED')"
	@echo "python: $$(uv run python --version 2>/dev/null || echo 'run: make sync')"
	@echo "node:   $$(command -v node >/dev/null 2>&1 && node --version || echo 'NOT INSTALLED')"
	@echo "npm:    $$(command -v npm >/dev/null 2>&1 && npm --version || echo 'NOT INSTALLED')"

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

.PHONY: clean
clean: ## Remove caches, the built UI, and local databases (keeps .venv/node_modules).
	rm -rf .ruff_cache .pytest_cache **/__pycache__ src/scorepilot/**/__pycache__
	rm -rf frontend/.svelte-kit frontend/build
	rm -f scorepilot.db
	find src/scorepilot/web -mindepth 1 ! -name index.html -delete 2>/dev/null || true

.PHONY: distclean
distclean: clean ## Also remove .venv and node_modules (full reset).
	rm -rf .venv frontend/node_modules
