#!/usr/bin/env bash
set -euo pipefail

SKILL_AGENT_HOST="${SKILL_AGENT_HOST:-127.0.0.1}"
SKILL_AGENT_PORT="${SKILL_AGENT_PORT:-18100}"

python3 -m uvicorn app:app --host "$SKILL_AGENT_HOST" --port "$SKILL_AGENT_PORT" --reload
