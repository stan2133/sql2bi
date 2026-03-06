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


if __name__ == "__main__":
    unittest.main()
