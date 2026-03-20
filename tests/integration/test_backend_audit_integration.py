from __future__ import annotations

import json
import os
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
SAMPLE_SQL_MD = REPO_ROOT / "sample.sql.md"
QUERY_CATALOG_PATH = REPO_ROOT / "services" / "backend" / "data" / "artifacts" / "query_catalog.json"


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
    timeout: float = 20.0,
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
            status = int(resp.status)
            body = resp.read().decode("utf-8")
            return status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        parsed: dict
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"detail": body}
        return int(exc.code), parsed


def _http_raw(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
) -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(url=url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read(), dict(resp.headers.items())
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read(), dict(exc.headers.items())


class BackendAuditIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
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
        raise RuntimeError(f"Backend failed to start. last_error={last_error}\n{output}")

    def test_import_query_and_persist_session_audit(self) -> None:
        status, imported = _http_json(
            "POST",
            f"{self.base_url}/api/v1/import/sql-md",
            payload={"sql_md_path": str(SAMPLE_SQL_MD)},
        )
        self.assertEqual(status, 200, imported)
        self.assertGreaterEqual(int(imported.get("query_count", 0)), 1)

        query_catalog = json.loads(QUERY_CATALOG_PATH.read_text(encoding="utf-8"))
        candidate = next((q for q in query_catalog.get("queries", []) if not q.get("datasource")), None)
        if candidate is None:
            candidate = (query_catalog.get("queries") or [{}])[0]
        query_id = str(candidate.get("id", "")).strip()
        self.assertTrue(query_id, "query id should not be empty")

        session_id = f"it_{uuid.uuid4().hex[:12]}"
        status, data = _http_json(
            "GET",
            f"{self.base_url}/api/v1/queries/{query_id}/data",
            headers={"X-SQL2BI-Session": session_id},
        )
        self.assertEqual(status, 200, data)
        self.assertEqual(data.get("query_id"), query_id)
        self.assertEqual(data.get("session_id"), session_id)

        sql_md_path = Path(str(data.get("audit_sql_md_path", "")))
        sql_file_path = Path(str(data.get("audit_sql_file_path", "")))
        self.assertTrue(sql_md_path.exists(), f"missing file: {sql_md_path}")
        self.assertTrue(sql_file_path.exists(), f"missing file: {sql_file_path}")

        sql_md_text = sql_md_path.read_text(encoding="utf-8")
        sql_file_text = sql_file_path.read_text(encoding="utf-8")
        self.assertIn("SQL 审计记录", sql_md_text)
        self.assertIn(f"## 查询: `{query_id}`", sql_md_text)
        self.assertIn("`状态`: `PASS`", sql_md_text)
        self.assertIn(f"-- session_id: {session_id}", sql_file_text)
        self.assertIn(f"-- query_id: {query_id}", sql_file_text)

    def test_block_non_readonly_sql(self) -> None:
        blocked_query_id = f"blocked_ddl_{uuid.uuid4().hex[:8]}"
        blocked_sql_md = REPO_ROOT / "out" / "tests" / f"blocked_{uuid.uuid4().hex[:8]}.sql.md"
        blocked_sql_md.parent.mkdir(parents=True, exist_ok=True)
        blocked_sql_md.write_text(
            (
                "# Security\n\n"
                "## card: blocked ddl\n"
                f"- id: {blocked_query_id}\n\n"
                "```sql\n"
                "DROP TABLE orders;\n"
                "```\n"
            ),
            encoding="utf-8",
        )

        status, imported = _http_json(
            "POST",
            f"{self.base_url}/api/v1/import/sql-md",
            payload={"sql_md_path": str(blocked_sql_md)},
        )
        self.assertEqual(status, 200, imported)

        session_id = f"it_{uuid.uuid4().hex[:12]}"
        status, data = _http_json(
            "GET",
            f"{self.base_url}/api/v1/queries/{blocked_query_id}/data",
            headers={"X-SQL2BI-Session": session_id},
        )
        self.assertEqual(status, 400, data)
        detail = str(data.get("detail", ""))
        self.assertIn("Only read-only SELECT/WITH/EXPLAIN SQL is allowed", detail)

    def test_export_csv_and_generate_versioned_report(self) -> None:
        status, imported = _http_json(
            "POST",
            f"{self.base_url}/api/v1/import/sql-md",
            payload={"sql_md_path": str(SAMPLE_SQL_MD)},
        )
        self.assertEqual(status, 200, imported)

        query_catalog = json.loads(QUERY_CATALOG_PATH.read_text(encoding="utf-8"))
        candidate = next((q for q in query_catalog.get("queries", []) if not q.get("datasource")), None)
        if candidate is None:
            candidate = (query_catalog.get("queries") or [{}])[0]
        query_id = str(candidate.get("id", "")).strip()
        self.assertTrue(query_id, "query id should not be empty")

        session_id = f"it_report_{uuid.uuid4().hex[:10]}"
        status, body, headers = _http_raw(
            "GET",
            f"{self.base_url}/api/v1/queries/{query_id}/export.csv",
            headers={"X-SQL2BI-Session": session_id},
        )
        self.assertEqual(status, 200, body.decode("utf-8", errors="replace"))
        csv_text = body.decode("utf-8")
        self.assertGreaterEqual(len([line for line in csv_text.splitlines() if line.strip()]), 2)

        theme = f"it-report-{uuid.uuid4().hex[:8]}"
        status, report = _http_json(
            "POST",
            f"{self.base_url}/api/v1/reports/query/{query_id}",
            payload={"theme": theme, "filters": {}, "include_csv": True},
            headers={"X-SQL2BI-Session": session_id},
        )
        self.assertEqual(status, 200, report)
        self.assertEqual(report.get("theme"), theme)
        self.assertRegex(str(report.get("version", "")), r"^v\d{8}\.\d{3}$")

        artifacts = report.get("artifacts") or {}
        required_paths = [
            "report_md_path",
            "report_json_path",
            "analysis_trace_path",
            "evidence_index_path",
            "metadata_path",
            "csv_export_path",
            "sql_audit_report_path",
            "report_audit_report_path",
            "audit_sql_md_path",
            "audit_sql_file_path",
        ]
        for key in required_paths:
            path = Path(str(artifacts.get(key, "")))
            self.assertTrue(path.exists(), f"missing artifact for {key}: {path}")

        report_md_text = Path(str(artifacts["report_md_path"])).read_text(encoding="utf-8")
        self.assertIn("## 1. 执行摘要", report_md_text)
        self.assertIn(f"`{query_id}`", report_md_text)

        metadata = json.loads(Path(str(artifacts["metadata_path"])).read_text(encoding="utf-8"))
        self.assertEqual(metadata.get("theme"), theme)
        self.assertEqual(metadata.get("session_id"), session_id)
        self.assertEqual(metadata.get("artifacts", {}).get("audit_sql_md_path"), artifacts.get("audit_sql_md_path"))

        evidence_index = json.loads(Path(str(artifacts["evidence_index_path"])).read_text(encoding="utf-8"))
        mappings = evidence_index.get("mappings") or []
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings[0].get("query_ids"), [query_id])


if __name__ == "__main__":
    unittest.main()
