#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-15173}"

if [[ -d "$ROOT/frontend/node_modules" ]]; then
  cd "$ROOT/frontend"
  npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
  exit 0
fi

echo "[frontend] node_modules not found, using lite frontend on ${FRONTEND_HOST}:${FRONTEND_PORT}"
cd "$ROOT/frontend-lite"
FRONTEND_HOST="$FRONTEND_HOST" FRONTEND_PORT="$FRONTEND_PORT" python3 server.py
