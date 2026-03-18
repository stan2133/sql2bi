#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

FILES=(
  "requirements-dev.txt"
  "skills/sql-to-bi-builder/requirements-dev.txt"
)

fail=0

is_pinned_line() {
  local line="$1"
  [[ "$line" =~ ^[[:space:]]*$ ]] && return 0
  [[ "$line" =~ ^[[:space:]]*# ]] && return 0
  [[ "$line" =~ ^[[:space:]]*-[rc][[:space:]]+ ]] && return 0
  [[ "$line" =~ ^[[:space:]]*[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+([[:space:]]*;.*)?$ ]] && return 0
  return 1
}

extract_pyyaml_version() {
  local file="$1"
  local version
  version="$(grep -E '^PyYAML==[0-9][0-9A-Za-z._+-]*$' "$file" | sed -E 's/^PyYAML==//' | head -n1 || true)"
  echo "$version"
}

for file in "${FILES[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "[requirements-check] Missing file: $file" >&2
    fail=1
    continue
  fi

  while IFS= read -r line || [[ -n "$line" ]]; do
    if ! is_pinned_line "$line"; then
      echo "[requirements-check] Unpinned dependency in $file: $line" >&2
      fail=1
    fi
  done < "$file"
done

root_pyyaml="$(extract_pyyaml_version "requirements-dev.txt")"
skill_pyyaml="$(extract_pyyaml_version "skills/sql-to-bi-builder/requirements-dev.txt")"

if [[ -z "$root_pyyaml" || -z "$skill_pyyaml" ]]; then
  echo "[requirements-check] PyYAML pin missing in one of requirements-dev files." >&2
  fail=1
elif [[ "$root_pyyaml" != "$skill_pyyaml" ]]; then
  echo "[requirements-check] PyYAML version mismatch: root=$root_pyyaml skill=$skill_pyyaml" >&2
  fail=1
fi

if [[ -n "$root_pyyaml" ]]; then
  if ! grep -nF "PyYAML==$root_pyyaml" pyproject.toml >/dev/null 2>&1; then
    echo "[requirements-check] pyproject.toml dev dependency must pin PyYAML==$root_pyyaml" >&2
    fail=1
  fi
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

echo "[requirements-check] pinned dependency versions look good"
