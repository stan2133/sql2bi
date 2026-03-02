from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent
PIPELINE_DIR = REPO_ROOT / "skills" / "sql-to-bi-builder" / "scripts"
DATA_DIR = BASE_DIR / "data"
ARTIFACT_DIR = DATA_DIR / "artifacts"
STATE_FILE = DATA_DIR / "state_lite.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"dashboards": [], "current_dashboard_id": None}
    return read_json(STATE_FILE)


def save_state(state: dict) -> None:
    write_json(STATE_FILE, state)


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


def load_artifact(name: str) -> dict:
    path = ARTIFACT_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing artifact: {path}")
    return read_json(path)


def hash_seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


def try_number(text: str):
    t = text.strip()
    if not t:
        return None
    try:
        if "." in t:
            return float(t)
        return int(t)
    except ValueError:
        return None


def filter_rows(rows: list[dict], filters: dict[str, str]) -> tuple[list[dict], list[dict]]:
    out = rows
    applied = []

    for field, raw in filters.items():
        value = raw.strip()
        if not value:
            continue

        sample_row = out[0] if out else {}
        if field not in sample_row:
            continue

        if ".." in value:
            left, right = value.split("..", 1)

            def in_range(r: dict) -> bool:
                v = r.get(field)
                if v is None:
                    return False
                ok = True
                if left:
                    ln = try_number(left)
                    ok = ok and (v >= (ln if ln is not None else left))
                if right:
                    rn = try_number(right)
                    ok = ok and (v <= (rn if rn is not None else right))
                return ok

            out = [r for r in out if in_range(r)]
            applied.append({"field": field, "mode": "range", "value": value})
            continue

        if "," in value:
            items = [x.strip() for x in value.split(",") if x.strip()]
            num_items = [try_number(x) for x in items]
            if all(x is not None for x in num_items):
                item_set = set(num_items)
            else:
                item_set = set(items)
            out = [r for r in out if r.get(field) in item_set]
            applied.append({"field": field, "mode": "set", "value": value})
            continue

        n = try_number(value)
        if n is not None:
            out = [r for r in out if r.get(field) == n]
        else:
            out = [r for r in out if str(r.get(field)) == value]
        applied.append({"field": field, "mode": "eq", "value": value})

    return out, applied


def generate_rows(query_id: str, semantic: dict, filters: dict[str, str]) -> dict:
    dims = (semantic.get("time_fields") or []) + (semantic.get("dimensions") or [])
    metrics = semantic.get("metrics") or ["value"]

    dim = dims[0] if dims else "category"
    m1 = metrics[0]
    m2 = metrics[1] if len(metrics) > 1 else f"{m1}_2"

    seed = hash_seed(f"{query_id}|{'|'.join(f'{k}={v}' for k, v in sorted(filters.items()))}")

    labels = []
    if semantic.get("time_fields"):
        labels = [f"2024-01-{str(i).zfill(2)}" for i in range(1, 13)]
    else:
        labels = [f"{dim}_{i}" for i in range(1, 13)]

    rows = []
    for i, label in enumerate(labels):
        v1 = 70 + ((seed + i * 11) % 50) + i * 2
        v2 = 45 + ((seed + i * 7) % 30) + i
        rows.append({dim: label, m1: int(v1), m2: int(v2)})

    filtered_rows, applied = filter_rows(rows, filters)

    s1 = sum(int(r.get(m1, 0)) for r in filtered_rows)
    s2 = sum(int(r.get(m2, 0)) for r in filtered_rows)

    return {
        "dimension": dim,
        "metrics": [m1, m2],
        "rows": filtered_rows,
        "row_count": len(filtered_rows),
        "applied_filters": applied,
        "summary": {m1: float(s1), m2: float(s2)},
    }


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            if path == "/api/health":
                self._json(200, {"status": "ok", "time": now_iso(), "mode": "lite"})
                return

            if path == "/api/v1/dashboards":
                state = load_state()
                self._json(200, {"dashboards": state.get("dashboards", [])})
                return

            if path == "/api/v1/dashboard/current":
                self._json(200, load_artifact("dashboard.json"))
                return

            if path == "/api/v1/filters":
                dashboard = load_artifact("dashboard.json")
                page = (dashboard.get("pages") or [{}])[0]
                payload = {
                    "global_filters": page.get("global_filters", []),
                    "widget_filters": {w.get("query_id"): w.get("dsl_filters", []) for w in page.get("widgets", [])},
                }
                self._json(200, payload)
                return

            if path.startswith("/api/v1/queries/") and path.endswith("/data"):
                parts = path.split("/")
                if len(parts) < 6:
                    self._json(400, {"detail": "Invalid query path"})
                    return
                query_id = parts[4]

                dashboard = load_artifact("dashboard.json")
                semantic_catalog = load_artifact("semantic_catalog.json")

                widget = None
                for w in (dashboard.get("pages") or [{}])[0].get("widgets", []):
                    if w.get("query_id") == query_id:
                        widget = w
                        break
                if not widget:
                    self._json(404, {"detail": f"Unknown query_id: {query_id}"})
                    return

                semantic = {}
                for q in semantic_catalog.get("queries", []):
                    if q.get("id") == query_id:
                        semantic = q
                        break

                filters = {}
                for k, v in query.items():
                    if k == "include_filters":
                        continue
                    if not v:
                        continue
                    t = str(v[0]).strip()
                    if t:
                        filters[k] = t

                rows_payload = generate_rows(query_id, semantic, filters)
                out = {
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
                self._json(200, out)
                return

            self._json(404, {"detail": f"Not found: {path}"})
        except FileNotFoundError as e:
            self._json(400, {"detail": str(e)})
        except Exception as e:
            self._json(500, {"detail": str(e)})

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            if parsed.path != "/api/v1/import/sql-md":
                self._json(404, {"detail": f"Not found: {parsed.path}"})
                return

            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            body = json.loads(raw.decode("utf-8"))
            sql_md_path = str(body.get("sql_md_path", "")).strip()
            if not sql_md_path:
                self._json(400, {"detail": "sql_md_path is required"})
                return

            sql_md = Path(sql_md_path).expanduser().resolve()
            if not sql_md.exists() or not sql_md.is_file():
                self._json(400, {"detail": f"sql.md not found: {sql_md}"})
                return

            pipeline_generate(sql_md)

            dashboard = load_artifact("dashboard.json")
            query_catalog = load_artifact("query_catalog.json")

            dashboard_id = stable_dashboard_id(str(sql_md))
            imported_at = now_iso()

            state = load_state()
            dashboards = [d for d in state.get("dashboards", []) if d.get("id") != dashboard_id]
            dashboards.insert(
                0,
                {
                    "id": dashboard_id,
                    "name": dashboard.get("name", "SQL Generated Dashboard"),
                    "source_sql_md": str(sql_md),
                    "created_at": imported_at,
                    "updated_at": imported_at,
                },
            )
            new_state = {
                "dashboards": dashboards,
                "current_dashboard_id": dashboard_id,
                "sql_md_path": str(sql_md),
                "imported_at": imported_at,
            }
            save_state(new_state)

            self._json(
                200,
                {
                    "dashboard_id": dashboard_id,
                    "sql_md_path": str(sql_md),
                    "query_count": int(query_catalog.get("query_count", 0)),
                    "widget_count": int(len((dashboard.get("pages") or [{}])[0].get("widgets", []))),
                    "imported_at": imported_at,
                },
            )
        except subprocess.CalledProcessError as e:
            self._json(500, {"detail": f"Pipeline failed: {e}"})
        except Exception as e:
            self._json(500, {"detail": str(e)})


def main() -> None:
    parser = argparse.ArgumentParser(description="SQL2BI Lite backend service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18000)
    args = parser.parse_args()

    ensure_dirs()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"SQL2BI lite backend running at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
