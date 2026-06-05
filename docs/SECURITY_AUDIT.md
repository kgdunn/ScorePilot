# Security & maintainability audit

A black-hat / white-hat pass over ScorePilot. Each finding records the risk, the
exploit reasoning, and what was done about it. The app currently ships **no
authentication**, so every endpoint is reachable by anyone who can reach the
deployed instance (see the `deploy/` stack on a public Hetzner host) — that
raises the stakes for the server-side request and resource-exhaustion findings
below.

## Fixed in this pass

### 1. SSRF in the URL importer — *High* — fixed

`POST /api/datasets/from-url` fetched any `http(s)` URL server-side
(`_fetch_url` in `api/datasets.py`). The only check was the URL *scheme*, so an
unauthenticated caller could make the server request internal resources:

- cloud-metadata (`http://169.254.169.254/latest/meta-data/…`) — credential theft,
- loopback / internal admin ports (`http://127.0.0.1:…`),
- the compose-internal database host (`http://db:5432`) and other LAN services,
- and, because `urllib` follows redirects by default, a *public* URL could `302`
  to any of the above, bypassing a naive host check.

**Fix:** `_guard_public_url()` resolves the host and rejects any address that is
private, loopback, link-local (covers the metadata IP), reserved, multicast, or
unspecified — failing closed on anything it cannot classify. A custom
`HTTPRedirectHandler` (`_PublicOnlyRedirectHandler`) re-validates **every**
redirect hop, so a public→private bounce is refused too.

**Residual risk:** DNS rebinding (host resolves to a public IP at validation
time, then a private IP at connection time) is not fully closed — that needs
connecting to the validated IP directly with a pinned `Host` header. Acceptable
for now given the threat model; noted here so a future change can pin the IP.

### 2. Unbounded upload size — *Medium* — fixed

`POST /api/datasets` did `await file.read()`, reading the entire request body
into memory with no cap, while the URL path was already capped at 5 MB. A single
large unauthenticated POST could exhaust process memory (DoS).

**Fix:** `_read_capped()` streams the upload in 1 MB chunks and aborts with
`413` past `MAX_UPLOAD_BYTES` (100 MB) — generous for real spectral data, but
bounded.

### 3. Stale, drifting version string — *Maintenance* — fixed

`pyproject.toml` was at `0.9.2`, but `scorepilot/__init__.py` and the FastAPI
`version=` were hardcoded `"0.1.0"` and never updated, despite the per-PR bump
rule in `CLAUDE.md`. The running API advertised a version unrelated to the
release.

**Fix:** `__version__` is now derived from installed package metadata
(`importlib.metadata.version`), and `create_app()` passes it to FastAPI, so the
single source of truth is `pyproject.toml`.

## Observations worth tracking (not changed here)

- **No authentication / authorization, no rate limiting.** Every dataset and
  model is globally readable and writable. Fine for a single-user local launch,
  but the public deploy is effectively an open, unauthenticated compute/storage
  endpoint. A future auth layer (even a single shared token) is the highest-value
  next step.
- **Interactive API docs are always on** (`/api/docs`, `/api/openapi.json`).
  Harmless, but consider gating them behind a setting in production.
- **Decompression amplification.** A within-cap gzip/`.xlsx` upload can still
  expand to a large in-memory frame during parsing. The upload cap bounds the
  input but not the post-parse footprint; worth a row/column cap if abuse shows up.
- **Pandas `read_csv`/`ExcelFile` on untrusted input.** No formula/CSV-injection
  concern server-side (values are never re-emitted as a spreadsheet), but keep it
  in mind if an export feature is added.
