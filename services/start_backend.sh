#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/backend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-18000}"

if python3 - <<'PY' >/dev/null 2>&1
import fastapi  # noqa: F401
import uvicorn  # noqa: F401
import duckdb   # noqa: F401
import polars   # noqa: F401
import pandas   # noqa: F401
PY
then
  echo "[backend] using full mode (fastapi + duckdb + polars/pandas) on ${BACKEND_HOST}:${BACKEND_PORT}"
  BACKEND_HOST="$BACKEND_HOST" BACKEND_PORT="$BACKEND_PORT" bash run.sh
else
  echo "[backend] full dependencies unavailable, using lite mode on ${BACKEND_HOST}:${BACKEND_PORT}"
  python3 app_lite.py --host "$BACKEND_HOST" --port "$BACKEND_PORT"
fi
