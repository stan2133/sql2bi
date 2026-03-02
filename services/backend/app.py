from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import polars as pl
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent
PIPELINE_DIR = REPO_ROOT / "skills" / "sql-to-bi-builder" / "scripts"
DATA_DIR = BASE_DIR / "data"
ARTIFACT_DIR = DATA_DIR / "artifacts"
STATE_FILE = DATA_DIR / "state.json"
DB_PATH = DATA_DIR / "metadata.duckdb"

ARTIFACT_FILES = [
    "query_catalog.json",
    "semantic_catalog.json",
    "chart_plan.json",
    "dashboard.json",
]

app = FastAPI(title="SQL2BI Backend Service", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ImportSQLRequest(BaseModel):
    sql_md_path: str


class ImportSQLResponse(BaseModel):
    dashboard_id: str
    sql_md_path: str
    query_count: int
    widget_count: int
    imported_at: str


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_dashboard_id(sql_md_path: str) -> str:
    digest = hashlib.sha1(sql_md_path.encode("utf-8")).hexdigest()[:12]
    return f"db_{digest}"


def run_step(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def pipeline_generate(sql_md_path: Path) -> None:
    py = sys.executable
    query_catalog = ARTIFACT_DIR / "query_catalog.json"
    semantic_catalog = ARTIFACT_DIR / "semantic_catalog.json"
    chart_plan = ARTIFACT_DIR / "chart_plan.json"
    dashboard = ARTIFACT_DIR / "dashboard.json"

    run_step([py, str(PIPELINE_DIR / "parse_sql_md.py"), "--input", str(sql_md_path), "--output", str(query_catalog)])
    run_step([py, str(PIPELINE_DIR / "infer_semantics.py"), "--input", str(query_catalog), "--output", str(semantic_catalog)])
    run_step([
        py,
        str(PIPELINE_DIR / "recommend_chart.py"),
        "--input",
        str(semantic_catalog),
        "--query-catalog",
        str(query_catalog),
        "--output",
        str(chart_plan),
    ])
    run_step([
        py,
        str(PIPELINE_DIR / "build_dashboard_spec.py"),
        "--queries",
        str(query_catalog),
        "--semantics",
        str(semantic_catalog),
        "--charts",
        str(chart_plan),
        "--output",
        str(dashboard),
    ])


def load_artifact(name: str) -> dict[str, Any]:
    p = ARTIFACT_DIR / name
    if not p.exists():
        raise FileNotFoundError(f"Missing artifact: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def ensure_db() -> None:
    con = duckdb.connect(str(DB_PATH))
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS dashboards (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source_sql_md TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS queries (
                id TEXT PRIMARY KEY,
                dashboard_id TEXT NOT NULL,
                title TEXT,
                sql_text TEXT NOT NULL,
                datasource TEXT,
                refresh TEXT,
                chart_hint TEXT,
                semantic_json TEXT,
                FOREIGN KEY(dashboard_id) REFERENCES dashboards(id)
            );
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS widgets (
                id TEXT PRIMARY KEY,
                dashboard_id TEXT NOT NULL,
                query_id TEXT NOT NULL,
                title TEXT,
                chart_type TEXT,
                x INTEGER,
                y INTEGER,
                w INTEGER,
                h INTEGER,
                filters_json TEXT,
                dsl_filters_json TEXT,
                FOREIGN KEY(dashboard_id) REFERENCES dashboards(id)
            );
            """
        )
    finally:
        con.close()


def index_metadata(dashboard_id: str, source_sql_md: str) -> tuple[int, int]:
    dashboard = load_artifact("dashboard.json")
    query_catalog = load_artifact("query_catalog.json")
    semantic_catalog = load_artifact("semantic_catalog.json")

    page = (dashboard.get("pages") or [{}])[0]
    widgets = page.get("widgets") or []

    semantic_by_id = {q.get("id"): q for q in semantic_catalog.get("queries", [])}

    con = duckdb.connect(str(DB_PATH))
    try:
        ts = now_iso()
        con.execute("DELETE FROM widgets WHERE dashboard_id = ?", [dashboard_id])
        con.execute("DELETE FROM queries WHERE dashboard_id = ?", [dashboard_id])
        con.execute("DELETE FROM dashboards WHERE id = ?", [dashboard_id])

        con.execute(
            "INSERT INTO dashboards (id, name, source_sql_md, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            [dashboard_id, dashboard.get("name", "SQL Generated Dashboard"), source_sql_md, ts, ts],
        )

        for q in query_catalog.get("queries", []):
            qid = q.get("id")
            if not qid:
                continue
            con.execute(
                """
                INSERT INTO queries (id, dashboard_id, title, sql_text, datasource, refresh, chart_hint, semantic_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    qid,
                    dashboard_id,
                    q.get("title", ""),
                    q.get("sql", ""),
                    q.get("datasource", ""),
                    q.get("refresh", ""),
                    q.get("chart_hint", "auto"),
                    json.dumps(semantic_by_id.get(qid, {}), ensure_ascii=False),
                ],
            )

        for w in widgets:
            wid = w.get("id")
            if not wid:
                continue
            pos = w.get("position") or {}
            con.execute(
                """
                INSERT INTO widgets (
                    id, dashboard_id, query_id, title, chart_type, x, y, w, h, filters_json, dsl_filters_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    wid,
                    dashboard_id,
                    w.get("query_id", ""),
                    w.get("title", ""),
                    w.get("chart", "table"),
                    int(pos.get("x", 0)),
                    int(pos.get("y", 0)),
                    int(pos.get("w", 6)),
                    int(pos.get("h", 4)),
                    json.dumps(w.get("filters", []), ensure_ascii=False),
                    json.dumps(w.get("dsl_filters", []), ensure_ascii=False),
                ],
            )

        return len(query_catalog.get("queries", [])), len(widgets)
    finally:
        con.close()


def get_active_dashboard_id() -> str:
    state = load_state()
    dashboard_id = state.get("dashboard_id")
    if not dashboard_id:
        raise HTTPException(status_code=400, detail="No imported sql.md. Call POST /api/v1/import/sql-md first.")
    return dashboard_id


def get_semantic_for_query(query_id: str) -> dict[str, Any]:
    con = duckdb.connect(str(DB_PATH))
    try:
        row = con.execute("SELECT semantic_json FROM queries WHERE id = ?", [query_id]).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Unknown query_id: {query_id}")
        return json.loads(row[0] or "{}")
    finally:
        con.close()


def get_widget_for_query(query_id: str) -> dict[str, Any]:
    dashboard = load_artifact("dashboard.json")
    page = (dashboard.get("pages") or [{}])[0]
    for w in page.get("widgets", []):
        if w.get("query_id") == query_id:
            return w
    raise HTTPException(status_code=404, detail=f"Unknown query_id: {query_id}")


def hash_seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


def _build_base_frame(query_id: str, semantic: dict[str, Any], filters: dict[str, str]) -> tuple[pl.DataFrame, str, str, str]:
    dims = (semantic.get("time_fields") or []) + (semantic.get("dimensions") or [])
    metrics = semantic.get("metrics") or ["value"]

    dim = dims[0] if dims else "category"
    m1 = metrics[0]
    m2 = metrics[1] if len(metrics) > 1 else f"{m1}_2"

    filter_key = "|".join(f"{k}={v}" for k, v in sorted(filters.items()))
    seed = hash_seed(f"{query_id}|{filter_key}")

    if semantic.get("time_fields"):
        labels = [f"2024-01-{str(i).zfill(2)}" for i in range(1, 13)]
    else:
        labels = [f"{dim}_{i}" for i in range(1, 13)]

    boost = 1 + min(len(filter_key), 24) / 120
    rows = []
    for i, label in enumerate(labels):
        v1 = int((70 + (seed + i * 11) % 50 + i * 2) * boost)
        v2 = int((45 + (seed + i * 7) % 30 + i) * boost)
        rows.append({dim: label, m1: v1, m2: v2})

    return pl.DataFrame(rows), dim, m1, m2


def _try_number(text: str) -> int | float | None:
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
        try:
            return int(stripped)
        except ValueError:
            return None
    try:
        return float(stripped)
    except ValueError:
        return None


def _apply_filters(df: pl.DataFrame, filters: dict[str, str]) -> tuple[pl.DataFrame, list[dict[str, str]]]:
    out = df
    applied: list[dict[str, str]] = []

    for field, raw_value in filters.items():
        if field not in out.columns:
            continue

        value = raw_value.strip()
        if not value:
            continue

        # Range filter syntax: "from..to"
        if ".." in value:
            left, right = value.split("..", 1)
            expr = pl.lit(True)

            left_num = _try_number(left)
            right_num = _try_number(right)

            if left:
                expr = expr & (
                    pl.col(field) >= pl.lit(left_num if left_num is not None else left)
                )
            if right:
                expr = expr & (
                    pl.col(field) <= pl.lit(right_num if right_num is not None else right)
                )

            out = out.filter(expr)
            applied.append({"field": field, "mode": "range", "value": value})
            continue

        # Set filter syntax: "a,b,c"
        if "," in value:
            items = [v.strip() for v in value.split(",") if v.strip()]
            num_items = [_try_number(v) for v in items]
            if all(v is not None for v in num_items):
                out = out.filter(pl.col(field).is_in([v for v in num_items if v is not None]))
            else:
                out = out.filter(pl.col(field).is_in(items))
            applied.append({"field": field, "mode": "set", "value": value})
            continue

        number_value = _try_number(value)
        if number_value is not None:
            out = out.filter(pl.col(field) == number_value)
        else:
            out = out.filter(pl.col(field).cast(pl.Utf8) == value)
        applied.append({"field": field, "mode": "eq", "value": value})

    return out, applied


def generate_query_rows(query_id: str, semantic: dict[str, Any], filters: dict[str, str]) -> dict[str, Any]:
    base_df, dim, m1, m2 = _build_base_frame(query_id, semantic, filters)
    filtered_df, applied_filters = _apply_filters(base_df, filters)

    # Polars is the primary engine for grouping and ordering.
    grouped_df = (
        filtered_df.group_by(dim)
        .agg(
            [
                pl.col(m1).sum().alias(m1),
                pl.col(m2).sum().alias(m2),
            ]
        )
        .sort(dim)
    )

    # Pandas is used for compatibility-oriented row export and summaries.
    pd_df = pd.DataFrame(grouped_df.to_dicts())
    rows = pd_df.to_dict(orient="records")

    summary = {
        m1: float(pd_df[m1].sum()) if m1 in pd_df.columns and not pd_df.empty else 0.0,
        m2: float(pd_df[m2].sum()) if m2 in pd_df.columns and not pd_df.empty else 0.0,
    }

    return {
        "dimension": dim,
        "metrics": [m1, m2],
        "rows": rows,
        "row_count": len(rows),
        "applied_filters": applied_filters,
        "summary": summary,
    }


@app.on_event("startup")
def startup() -> None:
    ensure_dirs()
    ensure_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": now_iso()}


@app.post("/api/v1/import/sql-md", response_model=ImportSQLResponse)
def import_sql_md(req: ImportSQLRequest) -> ImportSQLResponse:
    sql_md = Path(req.sql_md_path).expanduser().resolve()
    if not sql_md.exists() or not sql_md.is_file():
        raise HTTPException(status_code=400, detail=f"sql.md not found: {sql_md}")

    try:
        pipeline_generate(sql_md)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}") from e

    dashboard_id = stable_dashboard_id(str(sql_md))
    query_count, widget_count = index_metadata(dashboard_id, str(sql_md))

    state = {
        "dashboard_id": dashboard_id,
        "sql_md_path": str(sql_md),
        "imported_at": now_iso(),
    }
    save_state(state)

    return ImportSQLResponse(
        dashboard_id=dashboard_id,
        sql_md_path=str(sql_md),
        query_count=query_count,
        widget_count=widget_count,
        imported_at=state["imported_at"],
    )


@app.get("/api/v1/dashboards")
def list_dashboards() -> dict[str, Any]:
    con = duckdb.connect(str(DB_PATH))
    try:
        rows = con.execute(
            "SELECT id, name, source_sql_md, created_at, updated_at FROM dashboards ORDER BY updated_at DESC"
        ).fetchall()
    finally:
        con.close()

    items = [
        {
            "id": r[0],
            "name": r[1],
            "source_sql_md": r[2],
            "created_at": r[3],
            "updated_at": r[4],
        }
        for r in rows
    ]
    return {"dashboards": items}


@app.get("/api/v1/dashboard/current")
def get_current_dashboard() -> dict[str, Any]:
    _ = get_active_dashboard_id()
    return load_artifact("dashboard.json")


@app.get("/api/v1/filters")
def get_filters() -> dict[str, Any]:
    _ = get_active_dashboard_id()
    dashboard = load_artifact("dashboard.json")
    page = (dashboard.get("pages") or [{}])[0]
    return {
        "global_filters": page.get("global_filters", []),
        "widget_filters": {
            w.get("query_id"): w.get("dsl_filters", []) for w in page.get("widgets", [])
        },
    }


@app.get("/api/v1/queries/{query_id}/data")
def get_query_data(request: Request, query_id: str, include_filters: bool = Query(True)) -> dict[str, Any]:
    _ = get_active_dashboard_id()

    widget = get_widget_for_query(query_id)
    semantic = get_semantic_for_query(query_id)

    filters: dict[str, str] = {}
    if include_filters:
        for key, value in request.query_params.items():
            if key == "include_filters":
                continue
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            filters[key] = text

    rows_payload = generate_query_rows(query_id, semantic, filters)
    return {
        "query_id": query_id,
        "filters": filters,
        "chart": widget.get("chart", "table"),
        "dimension": rows_payload["dimension"],
        "metrics": rows_payload["metrics"],
        "rows": rows_payload["rows"],
        "row_count": rows_payload["row_count"],
        "applied_filters": rows_payload["applied_filters"],
        "summary": rows_payload["summary"],
        "generated_at": now_iso(),
    }
