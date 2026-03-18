#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-15173}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-18000}"
BACKEND_HEALTH_URL="${BACKEND_HEALTH_URL:-http://${BACKEND_HOST}:${BACKEND_PORT}/api/health}"

if command -v curl >/dev/null 2>&1; then
  if ! curl -fsS --max-time 1 "$BACKEND_HEALTH_URL" >/dev/null; then
    echo "[frontend] warning: backend not reachable at ${BACKEND_HEALTH_URL}" >&2
    echo "[frontend] tip: in another terminal run: bash services/start_backend.sh" >&2
  fi
fi

if [[ -d "$ROOT/frontend/node_modules" ]]; then
  cd "$ROOT/frontend"
  npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
  exit 0
fi

echo "[frontend] node_modules not found, using lite frontend on ${FRONTEND_HOST}:${FRONTEND_PORT}"
cd "$ROOT/frontend-lite"
FRONTEND_HOST="$FRONTEND_HOST" FRONTEND_PORT="$FRONTEND_PORT" python3 server.py
