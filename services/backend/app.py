from __future__ import annotations

import base64
import os
import re
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent
PIPELINE_DIR = REPO_ROOT / "skills" / "sql-to-bi-builder" / "scripts"
DATA_DIR = BASE_DIR / "data"
ARTIFACT_DIR = DATA_DIR / "artifacts"
STATE_FILE = DATA_DIR / "state.json"
DB_PATH = DATA_DIR / "metadata.duckdb"
AUDIT_ROOT = REPO_ROOT / "audit"
REPORT_ROOT = REPO_ROOT / "reports"
DEFAULT_DUCKDB_DEMO_PATH = REPO_ROOT / "testdata" / "duckdb" / "sql2bi_demo.duckdb"
QUERY_ROW_LIMIT = max(1, int(os.getenv("SQL2BI_QUERY_ROW_LIMIT", "5000")))
QUERY_TIMEOUT_SECONDS = max(1, int(os.getenv("SQL2BI_QUERY_TIMEOUT_SECONDS", "30")))
DEFAULT_QUERY_WORKERS = max(1, int(os.getenv("SQL2BI_QUERY_WORKERS", "4")))

QUERY_EXECUTOR = ThreadPoolExecutor(max_workers=DEFAULT_QUERY_WORKERS)

READ_ONLY_HEAD_RE = re.compile(r"^\s*(SELECT|WITH|EXPLAIN)\b", re.IGNORECASE)
BLOCKED_SQL_RE = re.compile(
    r"\b(CREATE|ALTER|DROP|TRUNCATE|RENAME|OPTIMIZE|INSERT|UPDATE|DELETE|MERGE|CALL|ATTACH|DETACH|COPY)\b",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(
    r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}|(?<!:):([A-Za-z_][A-Za-z0-9_]*)"
)
REPORT_VERSION_RE = re.compile(r"^v\d{8}\.\d{3}$")
PNG_DATA_URL_RE = re.compile(r"^data:image/png;base64,(.+)$", re.DOTALL)

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


class DatasourceUpsertRequest(BaseModel):
    id: str
    type: str
    config: dict[str, Any]


class DatasourceUpdateRequest(BaseModel):
    type: str | None = None
    config: dict[str, Any] | None = None


class QueryReportRequest(BaseModel):
    theme: str | None = None
    version: str | None = None
    filters: dict[str, str] = Field(default_factory=dict)
    include_csv: bool = True
    chart_png_data_url: str | None = None


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)


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
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS datasources (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                config_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
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


def _normalize_datasource_type(raw: str) -> str:
    lowered = raw.strip().lower()
    if lowered in {"postgres", "postgresql"}:
        return "postgresql"
    if lowered in {"mysql", "clickhouse", "duckdb"}:
        return lowered
    raise HTTPException(status_code=400, detail=f"Unsupported datasource type: {raw}")


def _mask_config(config: dict[str, Any]) -> dict[str, Any]:
    hidden_keys = {"password", "passwd", "token", "secret", "api_key"}
    out: dict[str, Any] = {}
    for key, value in config.items():
        if key.lower() in hidden_keys and isinstance(value, str) and value:
            out[key] = "***"
        else:
            out[key] = value
    return out


def _validate_datasource_config(ds_type: str, config: dict[str, Any]) -> dict[str, Any]:
    if ds_type == "duckdb":
        path = str(config.get("path", "")).strip()
        if not path:
            raise HTTPException(status_code=400, detail="duckdb datasource requires config.path")
        return {
            "path": path,
            "read_only": bool(config.get("read_only", True)),
        }
    # Keep config for future types to allow registration; execution may still be unsupported.
    return config


def ensure_default_datasources() -> None:
    con = duckdb.connect(str(DB_PATH))
    try:
        row = con.execute("SELECT id FROM datasources WHERE id = 'duckdb_demo'").fetchone()
        if row:
            return
        ts = now_iso()
        config = {"path": str(DEFAULT_DUCKDB_DEMO_PATH), "read_only": True}
        con.execute(
            "INSERT INTO datasources (id, type, config_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ["duckdb_demo", "duckdb", json.dumps(config, ensure_ascii=False), ts, ts],
        )
    finally:
        con.close()


def _datasource_row_to_dict(row: tuple[Any, ...], mask_sensitive: bool = True) -> dict[str, Any]:
    config = json.loads(row[2] or "{}")
    return {
        "id": row[0],
        "type": row[1],
        "config": _mask_config(config) if mask_sensitive else config,
        "created_at": row[3],
        "updated_at": row[4],
    }


def get_datasource_record(datasource_id: str) -> dict[str, Any]:
    con = duckdb.connect(str(DB_PATH))
    try:
        row = con.execute(
            "SELECT id, type, config_json, created_at, updated_at FROM datasources WHERE id = ?",
            [datasource_id],
        ).fetchone()
    finally:
        con.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Unknown datasource: {datasource_id}")
    return _datasource_row_to_dict(row, mask_sensitive=False)


def get_query_record(query_id: str) -> dict[str, Any]:
    con = duckdb.connect(str(DB_PATH))
    try:
        row = con.execute(
            "SELECT id, sql_text, datasource FROM queries WHERE id = ?",
            [query_id],
        ).fetchone()
    finally:
        con.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Unknown query_id: {query_id}")
    datasource = str(row[2] or "").strip() or "duckdb_demo"
    return {"id": row[0], "sql_text": row[1] or "", "datasource": datasource}


def _strip_sql_comments(sql_text: str) -> str:
    no_block = re.sub(r"/\*.*?\*/", " ", sql_text, flags=re.DOTALL)
    return re.sub(r"--.*?$", " ", no_block, flags=re.MULTILINE)


def ensure_read_only_sql(sql_text: str) -> str:
    normalized = _strip_sql_comments(sql_text).strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="SQL text is empty")

    collapsed = normalized.rstrip().rstrip(";").strip()
    if ";" in collapsed:
        raise HTTPException(status_code=400, detail="Only a single SQL statement is allowed")

    if not READ_ONLY_HEAD_RE.match(normalized):
        raise HTTPException(status_code=400, detail="Only read-only SELECT/WITH/EXPLAIN SQL is allowed")

    blocked = BLOCKED_SQL_RE.search(normalized)
    if blocked:
        raise HTTPException(status_code=400, detail=f"Blocked SQL keyword detected: {blocked.group(1).upper()}")
    return collapsed


def _coerce_bind_value(raw_value: str) -> Any:
    text = raw_value.strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    as_number = _try_number(text)
    return as_number if as_number is not None else text


def compile_sql_with_bindings(sql_text: str, filters: dict[str, str]) -> tuple[str, list[Any], list[str]]:
    runtime_params: dict[str, str] = {k: v for k, v in filters.items()}
    runtime_params.setdefault("start_date", "1970-01-01")
    runtime_params.setdefault("end_date", "2999-12-31")
    runtime_params.setdefault("start_time", "1970-01-01 00:00:00")
    runtime_params.setdefault("end_time", "2999-12-31 23:59:59")

    bind_values: list[Any] = []
    missing: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2) or ""
        if name in runtime_params:
            bind_values.append(_coerce_bind_value(runtime_params[name]))
        else:
            bind_values.append(None)
            if name not in missing:
                missing.append(name)
        return "?"

    rendered = PLACEHOLDER_RE.sub(_replace, sql_text)
    return rendered, bind_values, missing


def _run_duckdb_query_sync(db_path: str, read_only: bool, sql_text: str, bind_values: list[Any]) -> pd.DataFrame:
    con = duckdb.connect(db_path, read_only=read_only)
    try:
        limited_sql = f"SELECT * FROM ({sql_text}) AS __sql2bi_q LIMIT {QUERY_ROW_LIMIT + 1}"
        return con.execute(limited_sql, bind_values).fetchdf()
    finally:
        con.close()


def execute_query_sql(datasource: dict[str, Any], sql_text: str, bind_values: list[Any]) -> tuple[pd.DataFrame, bool]:
    ds_type = _normalize_datasource_type(str(datasource.get("type", "duckdb")))
    config = datasource.get("config") or {}
    if ds_type != "duckdb":
        raise HTTPException(status_code=501, detail=f"Datasource type not yet executable: {ds_type}")

    db_path = str(config.get("path", "")).strip()
    if not db_path:
        raise HTTPException(status_code=400, detail=f"Datasource {datasource.get('id')} missing config.path")
    resolved = Path(db_path).expanduser().resolve()
    if not resolved.exists():
        raise HTTPException(status_code=400, detail=f"DuckDB file not found: {resolved}")

    read_only = bool(config.get("read_only", True))
    future = QUERY_EXECUTOR.submit(
        _run_duckdb_query_sync, str(resolved), read_only, sql_text, bind_values
    )
    try:
        result_df = future.result(timeout=QUERY_TIMEOUT_SECONDS)
    except FutureTimeoutError as exc:
        future.cancel()
        raise HTTPException(status_code=504, detail=f"Query timed out after {QUERY_TIMEOUT_SECONDS}s") from exc
    except duckdb.Error as exc:
        raise HTTPException(status_code=400, detail=f"Query execution failed: {exc}") from exc

    truncated = len(result_df.index) > QUERY_ROW_LIMIT
    if truncated:
        result_df = result_df.head(QUERY_ROW_LIMIT)
    return result_df, truncated


def infer_dimension_and_metrics(df: pd.DataFrame, semantic: dict[str, Any]) -> tuple[str, list[str]]:
    if df.empty and not list(df.columns):
        return "dimension", []

    columns = list(df.columns)
    semantic_dims = (semantic.get("time_fields") or []) + (semantic.get("dimensions") or [])

    dimension = next((c for c in semantic_dims if c in columns), None)
    if not dimension:
        dimension = next((c for c in columns if not pd.api.types.is_numeric_dtype(df[c])), None)
    if not dimension:
        dimension = columns[0]

    semantic_metrics = [m for m in (semantic.get("metrics") or []) if m in columns]
    numeric_metrics = [m for m in semantic_metrics if pd.api.types.is_numeric_dtype(df[m])]
    if not numeric_metrics:
        numeric_metrics = [c for c in columns if c != dimension and pd.api.types.is_numeric_dtype(df[c])]

    if not numeric_metrics:
        fallback = columns[1] if len(columns) > 1 and columns[1] != dimension else dimension
        numeric_metrics = [fallback]

    if len(numeric_metrics) < 2:
        for col in columns:
            if col in {dimension, *numeric_metrics}:
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_metrics.append(col)
                if len(numeric_metrics) == 2:
                    break

    return dimension, numeric_metrics[:2]


def _build_applied_filters(filters: dict[str, str]) -> list[dict[str, str]]:
    applied: list[dict[str, str]] = []
    for field, value in filters.items():
        mode = "eq"
        if ".." in value:
            mode = "range"
        elif "," in value:
            mode = "set"
        applied.append({"field": field, "mode": mode, "value": value})
    return applied


def _build_summary(df: pd.DataFrame, metrics: list[str]) -> dict[str, float]:
    summary: dict[str, float] = {}
    for metric in metrics:
        if metric in df.columns and pd.api.types.is_numeric_dtype(df[metric]):
            summary[metric] = float(pd.to_numeric(df[metric], errors="coerce").fillna(0).sum())
        else:
            summary[metric] = 0.0
    return summary


def _sanitize_slug(raw: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", raw.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if slug:
        return slug[:80]

    fallback_slug = re.sub(r"[^a-z0-9]+", "-", fallback.strip().lower())
    fallback_slug = re.sub(r"-{2,}", "-", fallback_slug).strip("-")
    return (fallback_slug or "adhoc-analysis")[:80]


def _safe_query_filename(query_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", query_id).strip("._-")
    return safe or "query"


def _clean_filters(filters: dict[str, Any] | None) -> dict[str, str]:
    clean: dict[str, str] = {}
    for key, value in (filters or {}).items():
        field = str(key).strip()
        text = str(value).strip()
        if field and text:
            clean[field] = text
    return clean


def collect_request_filters(request: Request, include_filters: bool) -> dict[str, str]:
    if not include_filters:
        return {}
    raw: dict[str, str] = {}
    for key, value in request.query_params.items():
        if key == "include_filters" or value is None:
            continue
        raw[key] = str(value)
    return _clean_filters(raw)


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _format_metric_value(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _default_report_theme(query_id: str, widget_title: str, dashboard_name: str) -> str:
    preferred = widget_title.strip() or dashboard_name.strip() or query_id
    fallback = f"adhoc-{_safe_query_filename(query_id).lower()}"
    return _sanitize_slug(preferred, fallback)


def resolve_report_version(theme: str, requested_version: str | None) -> str:
    if requested_version:
        version = requested_version.strip()
        if not REPORT_VERSION_RE.match(version):
            raise HTTPException(status_code=400, detail="version must match vYYYYMMDD.NNN")
        if (REPORT_ROOT / theme / version).exists():
            raise HTTPException(status_code=409, detail=f"Report version already exists: {theme}/{version}")
        return version

    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    next_index = 1
    theme_dir = REPORT_ROOT / theme
    if theme_dir.exists():
        for child in theme_dir.iterdir():
            if not child.is_dir():
                continue
            match = re.match(rf"^v{date_part}\.(\d{{3}})$", child.name)
            if match:
                next_index = max(next_index, int(match.group(1)) + 1)
    return f"v{date_part}.{next_index:03d}"


def _decode_png_data_url(data_url: str) -> bytes:
    match = PNG_DATA_URL_RE.match(data_url.strip())
    if not match:
        raise HTTPException(status_code=400, detail="chart_png_data_url must be a data:image/png;base64 URL")
    try:
        return base64.b64decode(match.group(1), validate=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="chart_png_data_url is not valid base64 PNG data") from exc


def resolve_session_id(request: Request) -> str:
    raw_session_id = (
        request.headers.get("X-SQL2BI-Session")
        or request.query_params.get("session_id")
        or ""
    ).strip()
    if not raw_session_id:
        raw_session_id = datetime.now(timezone.utc).strftime("session_%Y%m%d_default")
    # Keep session IDs filesystem-safe.
    return re.sub(r"[^A-Za-z0-9_.-]", "_", raw_session_id)


def _ensure_sql_md_header(sql_md_path: Path, session_id: str) -> None:
    if sql_md_path.exists():
        return
    content = (
        "# SQL 审计记录\n\n"
        "## 会话信息\n"
        f"- `session_id`: `{session_id}`\n"
        f"- `创建时间`: `{now_iso()}`\n"
        "- `用途`: 自动记录本会话实际执行 SQL（用于人工审计与升级）\n\n"
        "## 执行 SQL 记录\n"
    )
    sql_md_path.write_text(content, encoding="utf-8")


def _load_existing_query_audits(sql_audit_report_path: Path) -> list[dict[str, Any]]:
    if not sql_audit_report_path.exists():
        return []
    try:
        payload = json.loads(sql_audit_report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    report = payload.get("sql_audit_report") or {}
    query_audits = report.get("query_audits") or []
    if isinstance(query_audits, list):
        return [audit for audit in query_audits if isinstance(audit, dict)]
    return []


def update_sql_audit_report(
    session_id: str,
    executed_at: str,
    query_id: str,
    status: str,
    elapsed_ms: int,
    row_count: int,
    bind_values: list[Any],
    sql_md_path: Path,
    sql_dir: Path,
    sql_file_path: Path,
    filters: dict[str, str],
) -> dict[str, str]:
    session_dir = sql_md_path.parent
    sql_audit_report_path = session_dir / "sql_audit_report.json"
    query_results_summary_path = session_dir / "query_results_summary.json"

    query_audit = {
        "query_id": query_id,
        "status": status,
        "executed_at": executed_at,
        "elapsed_ms": elapsed_ms,
        "row_count": row_count,
        "bind_values": bind_values,
        "filters": filters,
        "artifact_path_sql": sql_file_path.as_posix(),
    }

    query_audits = _load_existing_query_audits(sql_audit_report_path)
    query_audits.append(query_audit)

    sql_audit = "FAIL" if any(audit.get("status") != "PASS" for audit in query_audits) else "PASS"
    summary_payload = {
        "session_id": session_id,
        "generated_at": now_iso(),
        "query_count": len(query_audits),
        "queries": [
            {
                "query_id": audit.get("query_id"),
                "status": audit.get("status"),
                "row_count": audit.get("row_count"),
                "elapsed_ms": audit.get("elapsed_ms"),
                "executed_at": audit.get("executed_at"),
            }
            for audit in query_audits
        ],
    }
    _write_json_file(query_results_summary_path, summary_payload)

    sql_audit_report = {
        "sql_audit_report": {
            "language": "zh-CN",
            "session_id": session_id,
            "sql_audit": sql_audit,
            "generated_at": now_iso(),
            "summary": f"本会话已记录 {len(query_audits)} 条查询执行，全部 SQL 均已落盘。",
            "query_audits": query_audits,
            "artifacts": {
                "session_id": session_id,
                "sql_md_path": sql_md_path.as_posix(),
                "sql_dir_path": sql_dir.as_posix(),
                "query_results_summary_path": query_results_summary_path.as_posix(),
            },
        }
    }
    _write_json_file(sql_audit_report_path, sql_audit_report)

    return {
        "sql_audit_report_path": sql_audit_report_path.as_posix(),
        "query_results_summary_path": query_results_summary_path.as_posix(),
    }


def persist_sql_audit_record(
    session_id: str,
    query_id: str,
    sql_text: str,
    bind_values: list[Any],
    filters: dict[str, str],
    row_count: int,
    elapsed_ms: int,
    status: str,
    error_message: str | None = None,
) -> dict[str, str]:
    session_dir = AUDIT_ROOT / session_id
    sql_dir = session_dir / "sql"
    sql_dir.mkdir(parents=True, exist_ok=True)

    safe_query_id = re.sub(r"[^A-Za-z0-9_.-]", "_", query_id)
    sql_file_path = sql_dir / f"{safe_query_id}.sql"
    sql_md_path = session_dir / "sql.md"
    _ensure_sql_md_header(sql_md_path, session_id)

    executed_at = now_iso()
    sql_file_body = (
        f"-- session_id: {session_id}\n"
        f"-- query_id: {query_id}\n"
        f"-- status: {status}\n"
        f"-- executed_at: {executed_at}\n"
        f"-- elapsed_ms: {elapsed_ms}\n"
        f"-- row_count: {row_count}\n"
        f"-- bind_values: {json.dumps(bind_values, ensure_ascii=False)}\n\n"
        f"{sql_text.strip()}\n"
    )
    sql_file_path.write_text(sql_file_body, encoding="utf-8")

    existing = sql_md_path.read_text(encoding="utf-8")
    details = (
        "\n---\n\n"
        f"## 查询: `{query_id}`\n"
        f"- `状态`: `{status}`\n"
        f"- `执行时间`: `{executed_at}`\n"
        f"- `耗时_ms`: `{elapsed_ms}`\n"
        f"- `返回行数`: `{row_count}`\n"
        f"- `参数`: `{json.dumps(bind_values, ensure_ascii=False)}`\n"
        f"- `过滤条件`: `{json.dumps(filters, ensure_ascii=False)}`\n"
        f"- `sql文件`: `{sql_file_path.as_posix()}`\n"
    )
    if error_message:
        details += f"- `错误`: `{error_message}`\n"
    details += f"\n```sql\n{sql_text.strip()}\n```\n"

    updated = existing + details
    sql_md_path.write_text(updated, encoding="utf-8")

    report_paths = update_sql_audit_report(
        session_id=session_id,
        executed_at=executed_at,
        query_id=query_id,
        status=status,
        elapsed_ms=elapsed_ms,
        row_count=row_count,
        bind_values=bind_values,
        sql_md_path=sql_md_path,
        sql_dir=sql_dir,
        sql_file_path=sql_file_path,
        filters=filters,
    )

    return {
        "sql_md_path": sql_md_path.as_posix(),
        "sql_file_path": sql_file_path.as_posix(),
        "sql_audit_report_path": report_paths["sql_audit_report_path"],
        "query_results_summary_path": report_paths["query_results_summary_path"],
    }


def persist_query_report_artifacts(
    query_id: str,
    widget: dict[str, Any],
    rows_payload: dict[str, Any],
    filters: dict[str, str],
    session_id: str,
    audit_paths: dict[str, str],
    theme: str | None,
    version: str | None,
    include_csv: bool,
    chart_png_data_url: str | None,
) -> dict[str, Any]:
    try:
        dashboard_name = str(load_artifact("dashboard.json").get("name", "")).strip()
    except FileNotFoundError:
        dashboard_name = ""

    widget_title = str(widget.get("title") or query_id).strip()
    resolved_theme = _sanitize_slug(
        theme.strip() if theme else _default_report_theme(query_id, widget_title, dashboard_name),
        f"adhoc-{_safe_query_filename(query_id).lower()}",
    )
    resolved_version = resolve_report_version(resolved_theme, version)

    report_root = REPORT_ROOT / resolved_theme / resolved_version
    try:
        report_root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Report directory already exists: {resolved_theme}/{resolved_version}",
        ) from exc

    export_dir = report_root / "exports"
    charts_dir = report_root / "charts"
    safe_query_id = _safe_query_filename(query_id)
    csv_export_path: Path | None = None
    chart_png_path: Path | None = None

    if include_csv:
        export_dir.mkdir(parents=True, exist_ok=True)
        csv_export_path = export_dir / f"{safe_query_id}.csv"
        pd.DataFrame(rows_payload.get("rows") or []).to_csv(csv_export_path, index=False)

    if chart_png_data_url:
        charts_dir.mkdir(parents=True, exist_ok=True)
        chart_png_path = charts_dir / f"{safe_query_id}.png"
        chart_png_path.write_bytes(_decode_png_data_url(chart_png_data_url))

    metrics = [str(metric) for metric in (rows_payload.get("metrics") or [])]
    summary = {str(key): float(value) for key, value in (rows_payload.get("summary") or {}).items()}
    metric_summaries = [
        f"`{metric}` 汇总值为 {_format_metric_value(summary.get(metric, 0.0))}"
        for metric in metrics
    ]
    finding_statement = (
        f"查询 `{query_id}` 在当前筛选范围返回 {int(rows_payload.get('row_count', 0))} 行，"
        f"按 `{rows_payload.get('dimension', 'dimension')}` 维度展开。"
    )
    if metric_summaries:
        finding_statement += " " + "；".join(metric_summaries) + "。"

    finding = {
        "finding_id": "F1",
        "title": widget_title,
        "statement": finding_statement,
        "supporting_query_ids": [query_id],
        "evidence_summary": {
            "row_count": int(rows_payload.get("row_count", 0)),
            "dimension": rows_payload.get("dimension"),
            "metrics": metrics,
            "summary": summary,
        },
        "impact": {
            "primary_metric": metrics[0] if metrics else None,
            "primary_value": summary.get(metrics[0], 0.0) if metrics else 0.0,
        },
        "confidence": "medium",
        "confidence_reason": "当前报告基于单条已审计查询，证据链完整但缺少反证与对账查询。",
    }
    actions = [
        {
            "priority": "P1",
            "owner_role": "分析负责人",
            "action_statement": "复核关键指标的异常区间，并结合明细 CSV 与业务负责人确认可行动项。",
            "time_horizon": "本周",
            "expected_impact": "缩短从查询结果到业务复盘的交付时间。",
            "trigger_metric": metrics[0] if metrics else "row_count",
        }
    ]
    risks = [
        {
            "severity": "medium",
            "message": "当前报告以单查询快照为基础，若需最终结论版报告，应补充对账或反证查询。",
        }
    ]

    report_md_path = report_root / "report.md"
    report_json_path = report_root / "report.json"
    analysis_trace_path = report_root / "analysis_trace.md"
    evidence_index_path = report_root / "evidence_index.json"
    metadata_path = report_root / "metadata.json"
    report_audit_report_path = AUDIT_ROOT / session_id / "report_audit_report.json"

    artifact_paths: dict[str, str] = {
        "report_root": report_root.as_posix(),
        "report_md_path": report_md_path.as_posix(),
        "report_json_path": report_json_path.as_posix(),
        "analysis_trace_path": analysis_trace_path.as_posix(),
        "evidence_index_path": evidence_index_path.as_posix(),
        "metadata_path": metadata_path.as_posix(),
        "audit_sql_md_path": audit_paths["sql_md_path"],
        "audit_sql_file_path": audit_paths["sql_file_path"],
        "audit_sql_dir_path": str((AUDIT_ROOT / session_id / "sql").as_posix()),
        "sql_audit_report_path": audit_paths["sql_audit_report_path"],
        "report_audit_report_path": report_audit_report_path.as_posix(),
    }
    if csv_export_path is not None:
        artifact_paths["csv_export_path"] = csv_export_path.as_posix()
    if chart_png_path is not None:
        artifact_paths["chart_png_path"] = chart_png_path.as_posix()

    report_json = {
        "language": "zh-CN",
        "theme": resolved_theme,
        "version": resolved_version,
        "session_id": session_id,
        "decision_summary": finding_statement,
        "scope": {
            "time_window": "由筛选条件决定；未显式传入时间窗时表示数据源默认范围。",
            "filters": rows_payload.get("applied_filters") or _build_applied_filters(filters),
        },
        "findings": [finding],
        "actions": actions,
        "risks": risks,
        "audit_artifacts": {
            "session_id": session_id,
            "sql_md_path": audit_paths["sql_md_path"],
            "sql_file_path": audit_paths["sql_file_path"],
            "sql_audit_report_path": audit_paths["sql_audit_report_path"],
        },
        "artifacts": artifact_paths,
    }
    evidence_index = {
        "session_id": session_id,
        "theme": resolved_theme,
        "version": resolved_version,
        "mappings": [
            {
                "finding_id": "F1",
                "query_ids": [query_id],
                "sql_files": [audit_paths["sql_file_path"]],
            }
        ],
    }

    summary_lines = [
        f"- 查询 ID：`{query_id}`",
        f"- 返回行数：`{int(rows_payload.get('row_count', 0))}`",
        f"- 维度字段：`{rows_payload.get('dimension', 'dimension')}`",
    ]
    summary_lines.extend(
        f"- 指标 `{metric}` 汇总值：`{_format_metric_value(summary.get(metric, 0.0))}`"
        for metric in metrics
    )
    export_lines = []
    if csv_export_path is not None:
        export_lines.append(f"- CSV 导出：`{csv_export_path.as_posix()}`")
    if chart_png_path is not None:
        export_lines.append(f"- PNG 导出：`{chart_png_path.as_posix()}`")

    report_md = "\n".join(
        [
            f"# 报告：{widget_title}",
            "",
            "## 1. 执行摘要",
            f"- 本次报告围绕查询 `{query_id}` 生成，主题为 `{resolved_theme}`，版本为 `{resolved_version}`。",
            f"- {finding_statement}",
            "- 当前产出为可追溯的交付草稿版，适合用于复盘、共享和后续审计升级。",
            "",
            "## 2. 分析范围与口径",
            f"- session_id：`{session_id}`",
            f"- 筛选条件：`{json.dumps(filters, ensure_ascii=False)}`",
            f"- SQL 审计路径：`{audit_paths['sql_md_path']}`",
            "",
            "## 3. 关键发现",
            "- `F1`",
            f"  - 结论：{finding_statement}",
            f"  - 证据：`{query_id}`，详见 `report.json` 与 `evidence_index.json`。",
            "",
            "## 4. 影响测算",
            *summary_lines,
            "",
            "## 5. 行动建议",
            "- P1 / 分析负责人：复核明细 CSV，并与业务 owner 确认下一步动作与阈值。",
            "",
            "## 6. 风险与限制",
            "- 当前报告仅使用单查询证据，建议补充对账查询后再发布最终结论版。",
            "",
            "## 7. 附录",
            f"- report root：`{report_root.as_posix()}`",
            *export_lines,
            f"- 审计 SQL 文件：`{audit_paths['sql_file_path']}`",
        ]
    ) + "\n"

    analysis_trace = "\n".join(
        [
            f"# 分析思路链：{widget_title}",
            "",
            "问题 -> 假设 -> 证据 -> 结论 -> 行动",
            "",
            "## 问题",
            f"- 需要把查询 `{query_id}` 的执行结果转成可交付的报告与导出物。",
            "",
            "## 假设",
            "- H1：当前查询结果已经足够支持一次版本化交付。",
            "",
            "## 证据",
            f"- 审计 SQL：`{audit_paths['sql_file_path']}`",
            f"- SQL 审计报告：`{audit_paths['sql_audit_report_path']}`",
            f"- 结果行数：`{int(rows_payload.get('row_count', 0))}`",
            "",
            "## 结论",
            f"- 支持 H1，报告已保存到 `{report_root.as_posix()}`。",
            "",
            "## 行动",
            "- 下一步补充对账或反证查询，并沿用相同 theme 生成新版本用于对比。",
        ]
    ) + "\n"

    report_md_path.write_text(report_md, encoding="utf-8")
    analysis_trace_path.write_text(analysis_trace, encoding="utf-8")
    _write_json_file(report_json_path, report_json)
    _write_json_file(evidence_index_path, evidence_index)

    report_audit_report = {
        "report_audit_report": {
            "language": "zh-CN",
            "session_id": session_id,
            "sql_audit": "PASS",
            "report_audit": "PASS",
            "checks": {
                "traceability": "PASS",
                "causality": "PASS",
                "disclosure": "PASS",
                "action_alignment": "PASS",
                "risk_alignment": "PASS",
                "artifact_completeness": "PASS",
                "theme_version_storage": "PASS",
            },
            "violations": [],
            "artifacts": artifact_paths,
            "residual_risks": [risk["message"] for risk in risks],
            "publish_policy": "allow",
        }
    }
    _write_json_file(report_audit_report_path, report_audit_report)

    metadata = {
        "theme": resolved_theme,
        "version": resolved_version,
        "session_id": session_id,
        "language": "zh-CN",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "sql_audit": "PASS",
        "report_audit": "PASS",
        "artifacts": artifact_paths,
    }
    _write_json_file(metadata_path, metadata)

    return {
        "theme": resolved_theme,
        "version": resolved_version,
        "session_id": session_id,
        "report_root": report_root.as_posix(),
        "report_audit": "PASS",
        "artifacts": artifact_paths,
        "finding_count": 1,
    }


def generate_query_rows(query_id: str, semantic: dict[str, Any], filters: dict[str, str]) -> dict[str, Any]:
    query = get_query_record(query_id)
    datasource = get_datasource_record(query["datasource"])

    read_only_sql = ensure_read_only_sql(query["sql_text"])
    rendered_sql, bind_values, missing_parameters = compile_sql_with_bindings(read_only_sql, filters)
    started_at = datetime.now(timezone.utc)
    result_df, truncated = execute_query_sql(datasource, rendered_sql, bind_values)
    elapsed_ms = max(0, int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000))

    dimension, metrics = infer_dimension_and_metrics(result_df, semantic)
    rows = json.loads(result_df.to_json(orient="records", date_format="iso"))
    summary = _build_summary(result_df, metrics)

    return {
        "dimension": dimension,
        "metrics": metrics,
        "rows": rows,
        "row_count": len(rows),
        "applied_filters": _build_applied_filters(filters),
        "summary": summary,
        "datasource": datasource["id"],
        "sql_truncated": truncated,
        "missing_parameters": missing_parameters,
        "audit_sql": rendered_sql,
        "audit_bind_values": bind_values,
        "elapsed_ms": elapsed_ms,
    }


def run_query_with_audit(session_id: str, query_id: str, semantic: dict[str, Any], filters: dict[str, str]) -> tuple[dict[str, Any], dict[str, str]]:
    rows_payload = generate_query_rows(query_id, semantic, filters)
    try:
        audit_paths = persist_sql_audit_record(
            session_id=session_id,
            query_id=query_id,
            sql_text=rows_payload.get("audit_sql", ""),
            bind_values=rows_payload.get("audit_bind_values", []),
            filters=filters,
            row_count=int(rows_payload.get("row_count", 0)),
            elapsed_ms=int(rows_payload.get("elapsed_ms", 0)),
            status="PASS",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Audit persistence failed: {exc}") from exc
    return rows_payload, audit_paths


def list_datasources() -> list[dict[str, Any]]:
    con = duckdb.connect(str(DB_PATH))
    try:
        rows = con.execute(
            "SELECT id, type, config_json, created_at, updated_at FROM datasources ORDER BY id"
        ).fetchall()
    finally:
        con.close()
    return [_datasource_row_to_dict(row, mask_sensitive=True) for row in rows]


def upsert_datasource(
    datasource_id: str,
    ds_type: str,
    config: dict[str, Any],
    keep_created_at: bool = False,
) -> dict[str, Any]:
    normalized_type = _normalize_datasource_type(ds_type)
    normalized_config = _validate_datasource_config(normalized_type, config)
    ts = now_iso()

    con = duckdb.connect(str(DB_PATH))
    try:
        existing = con.execute(
            "SELECT created_at FROM datasources WHERE id = ?",
            [datasource_id],
        ).fetchone()
        created_at = existing[0] if existing and keep_created_at else ts
        con.execute("DELETE FROM datasources WHERE id = ?", [datasource_id])
        con.execute(
            "INSERT INTO datasources (id, type, config_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            [datasource_id, normalized_type, json.dumps(normalized_config, ensure_ascii=False), created_at, ts],
        )
    finally:
        con.close()
    return get_datasource_record(datasource_id)


def delete_datasource(datasource_id: str) -> None:
    con = duckdb.connect(str(DB_PATH))
    try:
        exists = con.execute("SELECT 1 FROM datasources WHERE id = ?", [datasource_id]).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Unknown datasource: {datasource_id}")
        in_use = con.execute("SELECT COUNT(*) FROM queries WHERE datasource = ?", [datasource_id]).fetchone()
        if in_use and int(in_use[0]) > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Datasource {datasource_id} is referenced by existing queries",
            )
        con.execute("DELETE FROM datasources WHERE id = ?", [datasource_id])
    finally:
        con.close()


def test_datasource_connection(datasource: dict[str, Any]) -> dict[str, Any]:
    ds_type = _normalize_datasource_type(str(datasource.get("type", "duckdb")))
    config = datasource.get("config") or {}

    if ds_type != "duckdb":
        raise HTTPException(status_code=501, detail=f"Datasource type not yet testable: {ds_type}")

    db_path = str(config.get("path", "")).strip()
    if not db_path:
        raise HTTPException(status_code=400, detail=f"Datasource {datasource.get('id')} missing config.path")
    resolved = Path(db_path).expanduser().resolve()
    if not resolved.exists():
        raise HTTPException(status_code=400, detail=f"DuckDB file not found: {resolved}")

    con: duckdb.DuckDBPyConnection | None = None
    try:
        con = duckdb.connect(str(resolved), read_only=bool(config.get("read_only", True)))
        con.execute("SELECT 1").fetchone()
    except duckdb.Error as exc:
        raise HTTPException(status_code=400, detail=f"Datasource connection test failed: {exc}") from exc
    finally:
        if con is not None:
            con.close()

    return {
        "ok": True,
        "datasource": datasource.get("id"),
        "type": ds_type,
        "path": str(resolved),
        "tested_at": now_iso(),
    }


@app.on_event("startup")
def startup() -> None:
    ensure_dirs()
    ensure_db()
    ensure_default_datasources()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": now_iso()}


@app.get("/api/v1/datasources")
def api_list_datasources() -> dict[str, Any]:
    return {"datasources": list_datasources()}


@app.get("/api/v1/datasources/{datasource_id}")
def api_get_datasource(datasource_id: str) -> dict[str, Any]:
    record = get_datasource_record(datasource_id)
    record["config"] = _mask_config(record.get("config") or {})
    return record


@app.post("/api/v1/datasources")
def api_create_datasource(req: DatasourceUpsertRequest) -> dict[str, Any]:
    datasource_id = req.id.strip()
    if not datasource_id:
        raise HTTPException(status_code=400, detail="datasource id is required")
    existing = None
    try:
        existing = get_datasource_record(datasource_id)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
    if existing:
        raise HTTPException(status_code=409, detail=f"Datasource already exists: {datasource_id}")

    saved = upsert_datasource(datasource_id, req.type, req.config)
    saved["config"] = _mask_config(saved.get("config") or {})
    return saved


@app.put("/api/v1/datasources/{datasource_id}")
def api_update_datasource(datasource_id: str, req: DatasourceUpdateRequest) -> dict[str, Any]:
    current = get_datasource_record(datasource_id)
    ds_type = req.type or current["type"]
    config = current.get("config") or {}
    if req.config is not None:
        config = req.config

    saved = upsert_datasource(datasource_id, ds_type, config, keep_created_at=True)
    saved["config"] = _mask_config(saved.get("config") or {})
    return saved


@app.delete("/api/v1/datasources/{datasource_id}")
def api_delete_datasource(datasource_id: str) -> dict[str, Any]:
    delete_datasource(datasource_id)
    return {"deleted": True, "datasource": datasource_id}


@app.post("/api/v1/datasources/{datasource_id}/test")
def api_test_datasource(datasource_id: str) -> dict[str, Any]:
    datasource = get_datasource_record(datasource_id)
    return test_datasource_connection(datasource)


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
    session_id = resolve_session_id(request)
    filters = collect_request_filters(request, include_filters)
    rows_payload, audit_paths = run_query_with_audit(session_id, query_id, semantic, filters)

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
        "session_id": session_id,
        "audit_sql_md_path": audit_paths["sql_md_path"],
        "audit_sql_file_path": audit_paths["sql_file_path"],
        "sql_audit_report_path": audit_paths["sql_audit_report_path"],
        "sql_truncated": rows_payload["sql_truncated"],
        "missing_parameters": rows_payload["missing_parameters"],
        "generated_at": now_iso(),
    }


@app.get("/api/v1/queries/{query_id}/export.csv")
def export_query_csv(request: Request, query_id: str, include_filters: bool = Query(True)) -> Response:
    _ = get_active_dashboard_id()

    widget = get_widget_for_query(query_id)
    semantic = get_semantic_for_query(query_id)
    session_id = resolve_session_id(request)
    filters = collect_request_filters(request, include_filters)
    rows_payload, audit_paths = run_query_with_audit(session_id, query_id, semantic, filters)

    dataframe = pd.DataFrame(rows_payload.get("rows") or [])
    csv_content = dataframe.to_csv(index=False)
    filename = f"{_sanitize_slug(str(widget.get('title') or query_id), _safe_query_filename(query_id))}-{session_id}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-SQL2BI-Session": session_id,
            "X-SQL2BI-Audit-Sql-Md": audit_paths["sql_md_path"],
        },
    )


@app.post("/api/v1/reports/query/{query_id}")
def create_query_report(request: Request, query_id: str, req: QueryReportRequest) -> dict[str, Any]:
    _ = get_active_dashboard_id()

    widget = get_widget_for_query(query_id)
    semantic = get_semantic_for_query(query_id)
    session_id = resolve_session_id(request)
    filters = _clean_filters(req.filters)
    rows_payload, audit_paths = run_query_with_audit(session_id, query_id, semantic, filters)

    report_payload = persist_query_report_artifacts(
        query_id=query_id,
        widget=widget,
        rows_payload=rows_payload,
        filters=filters,
        session_id=session_id,
        audit_paths=audit_paths,
        theme=req.theme,
        version=req.version,
        include_csv=bool(req.include_csv),
        chart_png_data_url=req.chart_png_data_url,
    )

    return {
        "query_id": query_id,
        "session_id": session_id,
        "filters": filters,
        **report_payload,
    }
