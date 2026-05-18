#!/usr/bin/env bash
# Build Lyzr-compatible ZIP packages for each CATAS skill.
# Each ZIP has SKILL.md at its root, alongside the Python module(s).
#
# Usage:
#   ./skills/package.sh                # build all three skills
#   ./skills/package.sh parse_ledger_data   # build just one
#
# Output: skills/_dist/<skill_name>.zip
set -euo pipefail

cd "$(dirname "$0")"

SKILLS=("parse_ledger_data" "trigger_mlro_alert" "write_audit_log")

if [ "$#" -gt 0 ]; then
  SKILLS=("$@")
fi

mkdir -p _dist

for skill in "${SKILLS[@]}"; do
  if [ ! -d "$skill" ]; then
    echo "skip: directory '$skill' not found" >&2
    continue
  fi
  if [ ! -f "$skill/SKILL.md" ]; then
    echo "skip: '$skill' is missing SKILL.md" >&2
    continue
  fi
  out="_dist/${skill}.zip"
  rm -f "$out"
  ( cd "$skill" && zip -qr "../_dist/${skill}.zip" . -x '__pycache__/*' '*.pyc' '*.DS_Store' )
  size=$(wc -c < "$out" | tr -d ' ')
  echo "built: $out (${size} bytes)"
done

echo
echo "Manifest:"
ls -lh _dist
