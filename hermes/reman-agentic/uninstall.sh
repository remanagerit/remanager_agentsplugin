#!/bin/sh
set -eu

HERMES_ROOT=${HERMES_HOME:-"$HOME/.hermes"}
TARGET_DIR="$HERMES_ROOT/plugins/reman-agentic"

case "$TARGET_DIR" in
  */plugins/reman-agentic) ;;
  *)
    printf '%s\n' "Refusing unsafe Hermes plugin path." >&2
    exit 1
    ;;
esac

if [ -L "$TARGET_DIR" ]; then
  printf '%s\n' "Refusing to remove a symlinked Hermes plugin." >&2
  exit 1
fi
if [ ! -e "$TARGET_DIR" ]; then
  printf '%s\n' "REman Agentic plugin is not installed."
  exit 0
fi
if [ ! -f "$TARGET_DIR/plugin.yaml" ] || ! grep -Eq '^name:[[:space:]]*reman-agentic[[:space:]]*$' "$TARGET_DIR/plugin.yaml"; then
  printf '%s\n' "Refusing to remove a directory without the REman plugin manifest." >&2
  exit 1
fi

rm -rf -- "$TARGET_DIR"
printf '%s\n' "Removed REman Agentic plugin from $TARGET_DIR"
