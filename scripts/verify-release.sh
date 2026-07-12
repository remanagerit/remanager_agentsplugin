#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
HERMES="$ROOT/hermes/reman-agentic"
OPENCLAW="$ROOT/openclaw/reman-agentic"

(cd "$ROOT" && python3 -m unittest hermes/reman-agentic/tests/test_connector.py)
cmp "$HERMES/skills/reman-accounting/SKILL.md" "$OPENCLAW/skills/reman-accounting/SKILL.md"

(
  cd "$OPENCLAW"
  npm ci
  npm run build
  npm test
  npm audit
  npm audit --omit=dev
  node "$ROOT/scripts/check-openclaw-dependencies.mjs"
  npm pack --json --dry-run
)

printf '%s\n' "REmanager connector release checks passed."
