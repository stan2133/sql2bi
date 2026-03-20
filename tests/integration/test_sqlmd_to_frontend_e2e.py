from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_SQL_MD = REPO_ROOT / "testdata" / "sql" / "e2e_duckdb.sql.md"
QUERY_CATALOG_PATH = REPO_ROOT / "services" / "backend" / "data" / "artifacts" / "query_catalog.json"
FRONTEND_RENDER_SCRIPT = REPO_ROOT / "tests" / "e2e" / "frontend_lite_render.mjs"


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_json(
    method: str,
    url: str,
    *,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict]:
    data = None
    req_headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url=url, method=method, data=data, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return int(resp.status), json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"detail": body}
        return int(exc.code), parsed


class SqlMdToFrontendE2EIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.node_bin = os.environ.get("SQL2BI_E2E_NODE", "node")
        if shutil.which(cls.node_bin) is None:
            raise unittest.SkipTest(f"node runtime not found: {cls.node_bin}")

        cls.port = _pick_free_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.process = subprocess.Popen(
            [
                os.environ.get("SQL2BI_TEST_PYTHON", sys.executable),
                "-m",
                "uvicorn",
                "services.backend.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.port),
            ],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        cls._wait_until_ready()

    @classmethod
    def tearDownClass(cls) -> None:
        if not hasattr(cls, "process"):
            return
        if cls.process.poll() is None:
            cls.process.terminate()
            try:
                cls.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cls.process.kill()
                cls.process.wait(timeout=5)

    @classmethod
    def _wait_until_ready(cls) -> None:
        deadline = time.time() + 30
        last_error = ""
        while time.time() < deadline:
            if cls.process.poll() is not None:
                break
            try:
                status, payload = _http_json("GET", f"{cls.base_url}/api/health", timeout=2.0)
                if status == 200 and payload.get("status") == "ok":
                    return
            except Exception as exc:  # pragma: no cover
                last_error = str(exc)
            time.sleep(0.3)

        output = ""
        if cls.process.stdout:
            output = cls.process.stdout.read()
        raise RuntimeError(f"[backend-startup] failed to start backend last_error={last_error}\n{output}")

    def _parse_last_json_line(self, output: str) -> dict:
        for line in reversed([l.strip() for l in output.splitlines() if l.strip()]):
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
        raise AssertionError(f"[frontend-render] no JSON result found in output:\n{output}")

    def test_sqlmd_pipeline_backend_frontend_e2e(self) -> None:
        # Stage 1: import sql.md and run pipeline.
        status, imported = _http_json(
            "POST",
            f"{self.base_url}/api/v1/import/sql-md",
            payload={"sql_md_path": str(E2E_SQL_MD)},
        )
        self.assertEqual(status, 200, f"[import-sqlmd] status={status}, body={imported}")
        self.assertGreaterEqual(int(imported.get("query_count", 0)), 1, f"[import-sqlmd] body={imported}")

        # Stage 2: backend contract checks for dashboard and query data.
        status, dashboard = _http_json("GET", f"{self.base_url}/api/v1/dashboard/current")
        self.assertEqual(status, 200, f"[backend-dashboard] status={status}, body={dashboard}")
        widgets = ((dashboard.get("pages") or [{}])[0]).get("widgets") or []
        self.assertGreaterEqual(len(widgets), 1, f"[backend-dashboard] body={dashboard}")

        query_catalog = json.loads(QUERY_CATALOG_PATH.read_text(encoding="utf-8"))
        query_id = str((query_catalog.get("queries") or [{}])[0].get("id", "")).strip()
        self.assertTrue(query_id, f"[query-catalog] invalid query_catalog={query_catalog}")

        session_id = f"it_e2e_{uuid.uuid4().hex[:10]}"
        status, query_data = _http_json(
            "GET",
            f"{self.base_url}/api/v1/queries/{query_id}/data",
            headers={"X-SQL2BI-Session": session_id},
        )
        self.assertEqual(status, 200, f"[backend-query] status={status}, body={query_data}")
        self.assertGreaterEqual(int(query_data.get("row_count", 0)), 1, f"[backend-query] body={query_data}")

        # Stage 3: audit artifact completeness.
        sql_md_path = Path(str(query_data.get("audit_sql_md_path", "")))
        sql_file_path = Path(str(query_data.get("audit_sql_file_path", "")))
        self.assertTrue(sql_md_path.exists(), f"[audit-sqlmd] missing file: {sql_md_path}")
        self.assertTrue(sql_file_path.exists(), f"[audit-sqlfile] missing file: {sql_file_path}")

        sql_md_text = sql_md_path.read_text(encoding="utf-8")
        sql_file_text = sql_file_path.read_text(encoding="utf-8")
        self.assertIn(f"## 查询: `{query_id}`", sql_md_text, "[audit-sqlmd] missing query id section")
        self.assertIn("`状态`: `PASS`", sql_md_text, "[audit-sqlmd] missing PASS status")
        self.assertIn("`返回行数`:", sql_md_text, "[audit-sqlmd] missing row count")
        self.assertIn("`参数`:", sql_md_text, "[audit-sqlmd] missing bind values")
        self.assertIn("```sql", sql_md_text, "[audit-sqlmd] missing SQL fenced block")
        self.assertIn(f"-- query_id: {query_id}", sql_file_text, "[audit-sqlfile] missing query id")
        self.assertIn("-- status: PASS", sql_file_text, "[audit-sqlfile] missing PASS status")

        # Stage 4: frontend rendering (DOM-level) using frontend-lite app code.
        proc = subprocess.run(
            [self.node_bin, str(FRONTEND_RENDER_SCRIPT), "--backend", self.base_url, "--timeout-ms", "30000"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            self.fail(f"[frontend-render] failed with code={proc.returncode}\n{proc.stdout}")

        render_payload = self._parse_last_json_line(proc.stdout)
        self.assertTrue(render_payload.get("ok"), f"[frontend-render] payload={render_payload}\n{proc.stdout}")
        self.assertGreaterEqual(
            int(render_payload.get("widgetCount", 0)),
            1,
            f"[frontend-render] expected at least one rendered widget, payload={render_payload}\n{proc.stdout}",
        )


if __name__ == "__main__":
    unittest.main()
