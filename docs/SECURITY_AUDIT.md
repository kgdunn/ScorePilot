# Security & maintainability audit

A black-hat / white-hat pass over ScorePilot. Each finding records the risk, the
exploit reasoning, and what was done about it.

The design is **local-first** (`uvx scorepilot` for a single scientist) with an
optional public deploy (the `deploy/` stack on a Hetzner host). The fixes follow
that grain: input-validation and resource bounds are always on, while the
access-control knobs (auth, docs visibility) are **opt-in/opt-out via settings**
so the local launch stays frictionless and a deploy can be locked down.

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

### 4. No authentication / authorization — *High (deploy)* — fixed (opt-in)

Every endpoint was world-readable and world-writable; the public deploy was an
open, unauthenticated compute/storage endpoint.

**Fix:** an optional HTTP Basic gate in `create_app()`, **inactive until
`SCOREPILOT_AUTH_PASSWORD` is set** so the local `uvx scorepilot` launch keeps
working with no login. When set, it covers the whole app (API, docs, and the
static SPA) using a constant-time credential check; `/api/health` stays open for
proxy/container health checks. The browser handles the credential prompt
natively, so the SPA needed no changes. Documented in `deploy/.env.example` and
`docs/DEPLOYMENT.md`.

### 5. Interactive API docs always on — *Low* — fixed (opt-out)

`/api/docs` and `/api/openapi.json` were always served. They're now gated by
`SCOREPILOT_DOCS_ENABLED` (default on for local use; the deploy `.env` turns them
off). With the auth gate enabled they're protected regardless.

### 6. Decompression / expansion amplification — *Medium* — fixed

A small-but-expansive upload (notably a zip-compressed `.xlsx`) could parse into a
huge in-memory frame even under the byte cap. A post-parse cell-count guard
(`max_cells`, default 50 M) now rejects oversized tables with `413`, and the byte
cap and cell cap are both configurable (`SCOREPILOT_MAX_UPLOAD_MB`,
`SCOREPILOT_MAX_CELLS`).

## Observations worth tracking (not changed here)

- **Rate limiting belongs at the reverse proxy.** Behind the host Caddy the app
  only sees the proxy's IP, so an in-process per-IP limiter would throttle all
  users together. `docs/DEPLOYMENT.md` now shows a Caddy `rate_limit` block, which
  sees real client IPs — the correct layer. The auth gate already stops anonymous
  abuse.
- **DNS rebinding (residual on the SSRF guard).** A host can resolve to a public
  IP at validation time and a private IP at connection time. Closing it fully
  means connecting to the validated IP with a pinned `Host` header (awkward with
  `urllib`); deferred and noted in finding #1.
- **Pandas `read_csv`/`ExcelFile` on untrusted input.** No formula/CSV-injection
  concern server-side (values are never re-emitted as a spreadsheet), but keep it
  in mind if an export feature is added.
