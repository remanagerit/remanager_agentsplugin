#!/bin/sh
set -eu

SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
HERMES_ROOT=${HERMES_HOME:-"$HOME/.hermes"}
TARGET_DIR="$HERMES_ROOT/plugins/reman-agentic"

mkdir -p "$TARGET_DIR"
for file in plugin.yaml __init__.py client.py file_access.py schemas.py tools.py README.md; do
  cp "$SOURCE_DIR/$file" "$TARGET_DIR/$file"
done
mkdir -p "$TARGET_DIR/skills"
cp -R "$SOURCE_DIR/skills/." "$TARGET_DIR/skills/"
chmod 700 "$TARGET_DIR"
chmod 600 "$TARGET_DIR"/*.py "$TARGET_DIR/plugin.yaml" "$TARGET_DIR/README.md"
find "$TARGET_DIR/skills" -type d -exec chmod 700 {} \;
find "$TARGET_DIR/skills" -type f -exec chmod 600 {} \;

printf '%s\n' "Installed REman Agentic plugin in $TARGET_DIR"
printf '%s\n' "Configure REMAN_AGENT_BASE_URL and REMAN_AGENT_TOKEN, then run: hermes plugins enable reman-agentic"
