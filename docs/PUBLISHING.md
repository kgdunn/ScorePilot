# Publishing to PyPI

Every push to `main` can publish a wheel to [PyPI](https://pypi.org) automatically
via `.github/workflows/publish.yml`. It is **off until you enable it**, so it never
fails before PyPI is configured.

## How it works

On push to `main` (or manual *Run workflow*), the job:

1. builds the Svelte frontend (so the wheel includes the UI),
2. sets a unique version `MAJOR.MINOR.<run_number>` derived from `pyproject.toml`
   (e.g. `0.1.0` -> `0.1.42`), so PyPI never sees a duplicate,
3. builds the wheel (`uv build --wheel`), and
4. publishes it with **Trusted Publishing** (OIDC) - no API token stored.

The job only runs when the repository variable `PYPI_PUBLISH` is `true`, and it
uses the `pypi` GitHub Environment.

## One-time setup

### 1. Reserve the name and configure Trusted Publishing on PyPI

The distribution name is `scorepilot` (from `pyproject.toml`). Make sure it is
available / owned by you on PyPI. Then add a **trusted publisher** so PyPI accepts
uploads from this workflow without a token:

- PyPI -> your project (or "Publishing" -> "Add a pending publisher" if the project
  does not exist yet) -> fill in:
  - **Owner:** `kgdunn`
  - **Repository:** `ScorePilot`
  - **Workflow name:** `publish.yml`
  - **Environment:** `pypi`

(See the [PyPI Trusted Publishing docs](https://docs.pypi.org/trusted-publishers/).)

### 2. Add the GitHub Environment and the switch

- Repo **Settings -> Environments -> New environment** named `pypi` (optionally add
  required reviewers to gate releases).
- Repo **Settings -> Secrets and variables -> Actions -> Variables -> New variable**:
  `PYPI_PUBLISH = true`.

That's it - the next merge to `main` publishes. Set `PYPI_PUBLISH` back to `false`
(or delete it) to pause publishing.

## Notes

- **Versioning.** Builds use `MAJOR.MINOR.<run_number>`; bump `MAJOR.MINOR` in
  `pyproject.toml` when you want a new series. For curated releases, you can instead
  rely on tags - tell me and I'll switch the trigger to tags/releases.
- **TestPyPI.** To rehearse against TestPyPI, set `repository-url:
  https://test.pypi.org/legacy/` in `publish.yml` and add a matching trusted
  publisher there.
- **Install the published build.** `uvx scorepilot` or `pipx install scorepilot`
  (or `pip install scorepilot`).
