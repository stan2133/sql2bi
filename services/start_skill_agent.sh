#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/skill_agent"

SKILL_AGENT_HOST="${SKILL_AGENT_HOST:-127.0.0.1}"
SKILL_AGENT_PORT="${SKILL_AGENT_PORT:-18100}"

if python3 - <<'PY' >/dev/null 2>&1
import fastapi   # noqa: F401
import uvicorn   # noqa: F401
import langchain # noqa: F401
PY
then
  echo "[skill-agent] using langchain mode on ${SKILL_AGENT_HOST}:${SKILL_AGENT_PORT}"
  SKILL_AGENT_HOST="$SKILL_AGENT_HOST" SKILL_AGENT_PORT="$SKILL_AGENT_PORT" bash run.sh
else
  echo "[skill-agent] dependencies unavailable. install:"
  echo "  pip install -r services/skill_agent/requirements.txt"
  exit 1
fi
