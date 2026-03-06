from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"
OUTPUT_ROOT = REPO_ROOT / "out" / "skill-agent"

SQL_TO_BI_SKILL_DIR = SKILLS_ROOT / "sql-to-bi-builder"
SQL_TO_BI_RUNNER = SQL_TO_BI_SKILL_DIR / "scripts" / "run_pipeline.py"
STARROCKS_SKILL_DIR = SKILLS_ROOT / "starrocks-mcp-analyst"

SUPPORTED_SKILLS = {
    "sql-to-bi-builder": SQL_TO_BI_SKILL_DIR,
    "starrocks-mcp-analyst": STARROCKS_SKILL_DIR,
}

DOMAIN_KEYWORDS: dict[str, str] = {
    "growth": "domains/growth-hacking.md",
    "增长": "domains/growth-hacking.md",
    "fraud": "domains/fraud-risk.md",
    "风控": "domains/fraud-risk.md",
    "nps": "domains/nps-cx.md",
    "满意度": "domains/nps-cx.md",
    "sales": "domains/sales-ops.md",
    "销售": "domains/sales-ops.md",
    "manufactur": "domains/manufacturing-ops.md",
    "制造": "domains/manufacturing-ops.md",
    "supply": "domains/supply-chain.md",
    "供应链": "domains/supply-chain.md",
    "finance": "domains/corporate-finance.md",
    "财务": "domains/corporate-finance.md",
    "hr": "domains/hr-people-ops.md",
    "人力": "domains/hr-people-ops.md",
}

app = FastAPI(title="SQL2BI Skill Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SkillStreamRequest(BaseModel):
    prompt: str = Field(..., description="Natural language request for skill execution")
    session_id: str | None = Field(default=None, description="Optional external session id")
    skills: list[str] | None = Field(default=None, description="Optional explicit skill order")
    sql_md_path: str | None = Field(default=None, description="sql.md path used by sql-to-bi-builder")
    output_root: str | None = Field(default=None, description="Root output directory for generated artifacts")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_session_id(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        value = datetime.now(timezone.utc).strftime("session_%Y%m%d_%H%M%S")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)


def _slugify(text: str, fallback: str = "analysis") -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fa5]+", "-", lowered)
    lowered = re.sub(r"-+", "-", lowered).strip("-")
    return lowered[:48] if lowered else fallback


def _tail_text(text: str, max_lines: int = 60) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:]) if len(lines) > max_lines else text


def _read_skill_description(skill_name: str) -> str:
    skill_md = SUPPORTED_SKILLS[skill_name] / "SKILL.md"
    if not skill_md.exists():
        return ""
    text = skill_md.read_text(encoding="utf-8")
    m = re.search(r"^description:\s*(.+)$", text, flags=re.MULTILINE)
    return m.group(1).strip() if m else ""


def _route_skills(payload: dict[str, Any]) -> dict[str, Any]:
    explicit = payload.get("skills") or []
    if explicit:
        selected: list[str] = []
        for skill in explicit:
            if skill not in SUPPORTED_SKILLS:
                raise HTTPException(status_code=400, detail=f"Unsupported skill: {skill}")
            selected.append(skill)
        payload["selected_skills"] = selected
        return payload

    prompt = str(payload.get("prompt", "")).lower()
    selected = []
    if any(k in prompt for k in ["sql.md", "dashboard", "bi", "图表", "仪表盘", "pipeline"]):
        selected.append("sql-to-bi-builder")
    if any(k in prompt for k in ["analysis", "insight", "分析", "mcp", "starrocks", "审计", "kpi"]):
        selected.append("starrocks-mcp-analyst")
    if not selected:
        selected = ["starrocks-mcp-analyst"]

    deduped = []
    for skill in selected:
        if skill not in deduped:
            deduped.append(skill)
    payload["selected_skills"] = deduped
    return payload


def _build_plan(payload: dict[str, Any]) -> dict[str, Any]:
    steps = []
    for idx, skill in enumerate(payload.get("selected_skills") or [], start=1):
        steps.append(
            {
                "step_id": idx,
                "skill": skill,
                "description": _read_skill_description(skill),
            }
        )
    payload["steps"] = steps
    return payload


PLANNING_CHAIN = RunnableLambda(_route_skills).with_config(run_name="skill_router") | RunnableLambda(_build_plan).with_config(
    run_name="plan_builder"
)


def run_sql_to_bi_builder(context: dict[str, Any]) -> dict[str, Any]:
    sql_md_path = context.get("sql_md_path")
    if not sql_md_path:
        sql_md_path = str(REPO_ROOT / "sample.sql.md")
    sql_md = Path(str(sql_md_path)).expanduser().resolve()
    if not sql_md.exists():
        raise FileNotFoundError(f"sql.md not found: {sql_md}")

    output_root = Path(str(context["output_root"])).expanduser().resolve()
    session_id = str(context["session_id"])
    out_dir = output_root / session_id / "bi"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(SQL_TO_BI_RUNNER),
        "--input",
        str(sql_md),
        "--out",
        str(out_dir),
        "--with-services",
    ]
    completed = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "sql-to-bi-builder failed: "
            f"code={completed.returncode}\nstdout:\n{_tail_text(completed.stdout)}\nstderr:\n{_tail_text(completed.stderr)}"
        )

    return {
        "status": "ok",
        "sql_md_path": str(sql_md),
        "out_dir": str(out_dir),
        "dashboard_path": str(out_dir / "dashboard.json"),
        "stdout_tail": _tail_text(completed.stdout),
    }


def _pick_domain_references(prompt: str) -> list[str]:
    lowered = prompt.lower()
    refs = []
    for keyword, rel in DOMAIN_KEYWORDS.items():
        if keyword in lowered and rel not in refs:
            refs.append(rel)
    if not refs:
        refs.append("step2-business-knowledge.md")
    return refs


def run_starrocks_mcp_analyst(context: dict[str, Any]) -> dict[str, Any]:
    prompt = str(context["prompt"]).strip()
    session_id = str(context["session_id"])
    output_root = Path(str(context["output_root"])).expanduser().resolve()

    theme = _slugify(prompt[:32], fallback="business-insight")
    version = datetime.now(timezone.utc).strftime("v%Y%m%d_%H%M%S")
    report_dir = output_root / session_id / "reports" / theme / version
    report_dir.mkdir(parents=True, exist_ok=True)

    refs = _pick_domain_references(prompt)
    references = [str((STARROCKS_SKILL_DIR / "references" / rel).resolve()) for rel in refs]

    decision_card_path = report_dir / "decision_card.md"
    analysis_plan_path = report_dir / "analysis_plan.md"

    decision_card = (
        "# Decision Card\n\n"
        f"- `session_id`: `{session_id}`\n"
        f"- `decision_question`: `{prompt}`\n"
        "- `target_metric`: `待补充（需结合业务定义）`\n"
        "- `analysis_window`: `待补充` \n"
        "- `comparison`: `待补充`\n"
        "- `scope`: `待补充`\n"
    )
    decision_card_path.write_text(decision_card, encoding="utf-8")

    plan_text = (
        "# StarRocks MCP Analyst Plan (Scaffold)\n\n"
        "## 说明\n"
        "- 当前为脚手架执行：完成 Step1~Step8 分析框架产物生成。\n"
        "- 未直接连接 StarRocks MCP server；请在下一阶段注入 MCP tool bindings。\n\n"
        "## 工作流\n"
        "1. 生成决策卡（Decision Card）\n"
        "2. 加载业务语义（增长/风控/NPS/销售/制造/供应链/财务/HR）\n"
        "3. 构建数据映射与抽样计划（只读，禁 DDL）\n"
        "4. 形成假设树与验证计划\n"
        "5. 生成 SQL 包（baseline/decomposition/reconciliation）\n"
        "6. 执行 SQL 审计（公式/粒度/Join 膨胀/对账/质量）\n"
        "7. 输出洞察与影响评估\n"
        "8. 执行报告审计并发布\n\n"
        "## 审计硬约束\n"
        "- 必须落盘：`audit/<session_id>/sql.md` 与 `audit/<session_id>/sql/<query_id>.sql`\n"
        "- SQL 落盘失败：`sql_audit=FAIL`，阻断发布。\n\n"
        "## 参考文件\n"
        + "\n".join(f"- `{ref}`" for ref in references)
        + "\n"
    )
    analysis_plan_path.write_text(plan_text, encoding="utf-8")

    return {
        "status": "ok",
        "theme": theme,
        "version": version,
        "report_dir": str(report_dir),
        "decision_card_path": str(decision_card_path),
        "analysis_plan_path": str(analysis_plan_path),
        "knowledge_references": references,
    }


SKILL_EXECUTORS = {
    "sql-to-bi-builder": run_sql_to_bi_builder,
    "starrocks-mcp-analyst": run_starrocks_mcp_analyst,
}


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": now_iso()}


@app.get("/api/v1/skills")
def list_skills() -> dict[str, Any]:
    items = []
    for skill_name, skill_dir in SUPPORTED_SKILLS.items():
        items.append(
            {
                "name": skill_name,
                "path": str(skill_dir),
                "description": _read_skill_description(skill_name),
            }
        )
    return {"skills": items}


@app.post("/api/v1/skills/stream")
async def stream_skill_run(req: SkillStreamRequest) -> StreamingResponse:
    base_payload = req.model_dump()
    base_payload["session_id"] = normalize_session_id(req.session_id)
    base_payload["output_root"] = str(
        Path(req.output_root).expanduser().resolve() if req.output_root else OUTPUT_ROOT.resolve()
    )

    async def event_generator():
        context = dict(base_payload)
        context["skill_results"] = {}

        yield _sse(
            "started",
            {
                "session_id": context["session_id"],
                "started_at": now_iso(),
                "prompt": context["prompt"],
            },
        )

        try:
            plan = PLANNING_CHAIN.invoke(context)
        except HTTPException as exc:
            yield _sse("error", {"session_id": context["session_id"], "detail": exc.detail, "status_code": exc.status_code})
            return
        except Exception as exc:
            yield _sse("error", {"session_id": context["session_id"], "detail": str(exc)})
            return

        context.update(plan)
        yield _sse(
            "plan",
            {
                "session_id": context["session_id"],
                "selected_skills": context.get("selected_skills", []),
                "steps": context.get("steps", []),
            },
        )

        for step in context.get("steps", []):
            skill = step["skill"]
            yield _sse(
                "skill_started",
                {
                    "session_id": context["session_id"],
                    "step_id": step["step_id"],
                    "skill": skill,
                    "at": now_iso(),
                },
            )

            try:
                result = await asyncio.to_thread(SKILL_EXECUTORS[skill], context)
            except Exception as exc:
                yield _sse(
                    "error",
                    {
                        "session_id": context["session_id"],
                        "step_id": step["step_id"],
                        "skill": skill,
                        "detail": str(exc),
                        "failed_at": now_iso(),
                    },
                )
                return

            context["skill_results"][skill] = result
            yield _sse(
                "skill_completed",
                {
                    "session_id": context["session_id"],
                    "step_id": step["step_id"],
                    "skill": skill,
                    "result": result,
                    "at": now_iso(),
                },
            )

        yield _sse(
            "completed",
            {
                "session_id": context["session_id"],
                "finished_at": now_iso(),
                "results": context["skill_results"],
            },
        )

    return StreamingResponse(event_generator(), media_type="text/event-stream")
