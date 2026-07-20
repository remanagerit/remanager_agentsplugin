#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OPENCLAW="$ROOT/openclaw/reman-agentic"

"$ROOT/scripts/verify-hermes-release.sh"

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
