from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_SQL_MD = REPO_ROOT / "sample.sql.md"


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _read_sse_events(url: str, payload: dict, timeout: float = 120.0) -> list[tuple[str, dict]]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )
    events: list[tuple[str, dict]] = []
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        event_name = ""
        event_data = ""
        for raw in resp:
            line = raw.decode("utf-8").rstrip("\n")
            stripped = line.strip()
            if not stripped:
                if event_name and event_data:
                    events.append((event_name, json.loads(event_data)))
                    if event_name in {"completed", "error"}:
                        break
                event_name = ""
                event_data = ""
                continue
            if stripped.startswith("event:"):
                event_name = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("data:"):
                event_data = stripped.split(":", 1)[1].strip()
    return events


class SkillAgentStreamIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _pick_free_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "services.skill_agent.app:app",
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
        while time.time() < deadline:
            if cls.process.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"{cls.base_url}/api/health", timeout=2) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    if int(resp.status) == 200 and payload.get("status") == "ok":
                        return
            except Exception:
                pass
            time.sleep(0.3)

        output = cls.process.stdout.read() if cls.process.stdout else ""
        raise RuntimeError(f"skill-agent failed to start:\n{output}")

    def test_stream_executes_two_skills(self) -> None:
        session_id = f"it_skill_agent_{uuid.uuid4().hex[:8]}"
        payload = {
            "prompt": "请先构建 BI dashboard，再给出业务分析计划",
            "session_id": session_id,
            "skills": ["sql-to-bi-builder", "starrocks-mcp-analyst"],
            "sql_md_path": str(SAMPLE_SQL_MD),
        }

        events = _read_sse_events(f"{self.base_url}/api/v1/skills/stream", payload, timeout=180)
        self.assertGreaterEqual(len(events), 4, events)

        names = [name for name, _ in events]
        self.assertIn("started", names)
        self.assertIn("plan", names)
        self.assertIn("skill_started", names)
        self.assertIn("skill_completed", names)
        self.assertEqual(names[-1], "completed", events)

        completed_payload = events[-1][1]
        results = completed_payload.get("results") or {}
        self.assertIn("sql-to-bi-builder", results)
        self.assertIn("starrocks-mcp-analyst", results)

        sql_result = results["sql-to-bi-builder"]
        report_result = results["starrocks-mcp-analyst"]
        self.assertTrue(Path(sql_result["dashboard_path"]).exists(), sql_result)
        self.assertTrue(Path(report_result["analysis_plan_path"]).exists(), report_result)
        self.assertTrue(Path(report_result["decision_card_path"]).exists(), report_result)


if __name__ == "__main__":
    unittest.main()
