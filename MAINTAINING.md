# Maintaining proxmox-dr-mcp

Runbook for maintaining this repository. It covers the CI pipeline, local
development, dependency updates, issue hygiene, and releases.

## CI

Workflow: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

- Triggered on pushes to `main` and on every pull request.
- Matrix: **Python 3.11, 3.12, 3.13** (Ubuntu).
- Steps: `uv sync --frozen --no-dev`, then the smoke and safety test suites:

  ```bash
  uv run python tests/test_smoke.py
  uv run python tests/test_safety.py
  ```

- `tests/test_live.py` is **not** part of CI — it requires a reachable Proxmox
  VE host and credentials (see [Local development](#local-development)).

A pull request must be green on all three Python versions before merging.

## Local development

Requirements: Python 3.11+ (3.13 recommended, see `.python-version`) and
[uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/piyush97/proxmox-dr-mcp.git
cd proxmox-dr-mcp
uv sync          # install dependencies into .venv (uses pyproject.toml + uv.lock)
```

`pyproject.toml` defines no `[dev]` extra — development tooling is a plain
`uv sync`. There is no separate dev-requirements file.

Run the test suites (matches CI):

```bash
uv run python tests/test_smoke.py
uv run python tests/test_safety.py
```

Run the live integration test (requires `PROXMOX_HOST`,
`PROXMOX_TOKEN_ID`, `PROXMOX_TOKEN_VALUE` from `.env` — see
[`.env.example`](.env.example) and README "Configuration"):

```bash
uv run python tests/test_live.py
```

Run the server locally:

```bash
uv run proxmox-dr-mcp
```

The server listens on HTTP (streamable-http) at `http://localhost:8080/mcp`
with a `GET /health` endpoint. `PORT` is configurable via the environment.

## Dependency updates (Dependabot)

Configuration: [`.github/dependabot.yml`](.github/dependabot.yml)

- **pip** ecosystem for `/` — updates the PEP 621 `project.dependencies` in
  `pyproject.toml` (the repo has no `requirements.txt`). Runs **weekly,
  Monday 06:00 UTC**, `open-pull-requests-limit: 5`. Minor and patch bumps are
  grouped into a single `pip-minor-patch` PR; major bumps open individually.
- **uv** ecosystem for `/` — keeps the committed `uv.lock` in sync with
  `pyproject.toml` (this repo's lockfile is uv-managed, not pip-generated).
- **github-actions** ecosystem for `/` — keeps pinned action versions current.
- **docker** ecosystem for `/` — tracks the `python:3.13-slim` base image in
  the [Dockerfile](Dockerfile).
- Dependabot does **not** run `uv sync` itself — CI does, and `ci.yml` uses
  `uv sync --frozen`, so a merged Dependabot PR that touched `uv.lock` is
  validated by the merge commit's CI run on all three Python versions.

Review Dependabot PRs like any other change: they must pass CI on all three
Python versions before merging. Dependabot PRs carry the `dependencies` label,
which exempts them from the stale workflow.

## Issue / PR hygiene (stale workflow)

Workflow: [`.github/workflows/stale.yml`](.github/workflows/stale.yml)

- Runs **every Monday 09:00 UTC** (manual trigger via `workflow_dispatch`
  also available).
- Issues inactive for **60 days** are labelled `stale`; PRs inactive for
  **30 days** are labelled `stale`.
- Nothing is ever auto-closed (`days-before-*-close: -1`). A human decides
  whether to close a stale issue/PR.
- PRs labelled `dependencies` are exempt (Dependabot PRs must not be marked
  stale while CI is pending).

## Releasing

No tags or releases exist yet. When cutting the first release:

1. Make sure `main` is green on CI (all three Python versions).
2. Update the version in `pyproject.toml` and add a `CHANGELOG.md` entry under
   a new `## vX.Y.Z` heading (keep the existing format).
3. Tag and push:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

4. Create a GitHub Release from the tag (title `vX.Y.Z`), listing the changes.
5. Publish to PyPI if desired: build with `uv build` and upload with
   `uv publish` (or `python -m build` + `twine upload`).

## MCP server

- The server is deployed on the MCPize marketplace (see README "Deploy on
  MCPize"); the `serverId` lives in [`.mcpize/project.json`](.mcpize/project.json).
- Containerized deployment uses the [Dockerfile](Dockerfile) (`uv sync --frozen
  --no-dev`, runs as non-root `nobody`, healthcheck on `/health`).
- Credentials are validated lazily at tool-call time — the server boots without
  a configured Proxmox token and returns a clear "credentials not configured"
  error per tool.
