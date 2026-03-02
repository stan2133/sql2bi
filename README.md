# SQL2BI Workspace

Turn `sql.md` (multiple SQL blocks in markdown) into a runnable BI prototype:
- SQL parsing
- semantic inference
- DSL filter extraction (P0)
- chart recommendation
- dashboard spec generation
- backend + frontend service integration

## Current Architecture

- Skill pipeline: `skills/sql-to-bi-builder/scripts/*`
- Backend service:
  - full mode: FastAPI + DuckDB + Polars + Pandas (`services/backend/app.py`)
  - lite mode: stdlib HTTP fallback (`services/backend/app_lite.py`)
- Frontend service:
  - full mode: React + Vite + ECharts (`services/frontend`)
  - lite mode: static HTML/JS + ECharts CDN (`services/frontend-lite`)
- Test fixtures:
  - SQL markdown: `testdata/sql/demo.sql.md`
  - DuckDB init SQL: `testdata/duckdb/init.sql`
  - Demo DB file: `testdata/duckdb/sql2bi_demo.duckdb`

## Python And Version Control (Python 3.11 + uv)

This repo is pinned to Python 3.11:
- `.python-version`: `3.11`
- `pyproject.toml`: `requires-python = ">=3.11,<3.12"`

Recommended setup with `uv`:

```bash
uv python pin 3.11
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -r requirements-dev.txt
uv pip install -r services/backend/requirements.txt
```

If `uv` is unavailable, use built-in scripts:

```bash
bash skills/sql-to-bi-builder/scripts/setup_venv.sh --with-dev
bash skills/sql-to-bi-builder/scripts/check_python311.sh --with-dev
```

## Run Services

Default ports:
- backend: `127.0.0.1:18000`
- frontend: `127.0.0.1:15173`

Start:

```bash
bash services/start_backend.sh
bash services/start_frontend.sh
```

Behavior:
- If backend Python deps are installed, backend runs in full mode.
- Otherwise backend falls back to lite mode automatically.
- If frontend `node_modules` exists, frontend runs React/Vite mode.
- Otherwise frontend falls back to static lite mode automatically.

## End-to-End: sql.md -> BI Artifacts

Run the skill pipeline (requires Python 3.11 runtime):

```bash
python3.11 skills/sql-to-bi-builder/scripts/run_pipeline.py \
  --input /abs/path/sql.md \
  --out /abs/path/out \
  --with-services
```

Generated files:
- `query_catalog.json`
- `semantic_catalog.json` (includes `dsl_filters`)
- `chart_plan.json`
- `dashboard.json` (includes page-level `global_filters`)
- `ui/` static scaffold
- `services/` generated service bundle

## Backend API (used by frontend)

- `GET /api/health`
- `POST /api/v1/import/sql-md` with body:
  - `{"sql_md_path": "/abs/path/to/sql.md"}`
- `GET /api/v1/dashboard/current`
- `GET /api/v1/filters`
- `GET /api/v1/queries/{query_id}/data?include_filters=true&field=value`

Example import:

```bash
curl -X POST http://127.0.0.1:18000/api/v1/import/sql-md \
  -H 'Content-Type: application/json' \
  -d '{"sql_md_path":"/Users/lyg/software/sql2bi/testdata/sql/demo.sql.md"}'
```

## Git Hooks

Install repo hooks:

```bash
bash scripts/install-git-hooks.sh
```

Hooks:
- `pre-commit`: conflict markers, shell/python syntax, requirement pin checks
- `pre-push`: smoke pipeline run on `sample.sql.md`

