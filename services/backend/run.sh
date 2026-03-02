#!/usr/bin/env bash
set -euo pipefail

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-18000}"

python3 -m uvicorn app:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload
