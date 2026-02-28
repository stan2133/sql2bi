#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d .git ]]; then
  echo "Not a git repository: $ROOT_DIR" >&2
  exit 1
fi

chmod +x .githooks/pre-commit .githooks/pre-push
git config core.hooksPath .githooks

echo "Installed git hooks path: .githooks"
echo "Try: .githooks/pre-commit"
