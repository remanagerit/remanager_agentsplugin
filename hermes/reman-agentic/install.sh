#!/bin/sh
set -eu

umask 077
SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
HERMES_ROOT=${HERMES_HOME:-"$HOME/.hermes"}
PLUGINS_DIR="$HERMES_ROOT/plugins"
TARGET_DIR="$PLUGINS_DIR/reman-agentic"
STAGING_DIR="$PLUGINS_DIR/.reman-agentic-install-$$"

if [ -e "$TARGET_DIR" ] || [ -L "$TARGET_DIR" ]; then
  printf '%s\n' "Refusing to replace existing Hermes plugin: $TARGET_DIR" >&2
  exit 1
fi

cleanup() {
  rm -rf -- "$STAGING_DIR"
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$PLUGINS_DIR" "$STAGING_DIR"
for file in plugin.yaml __init__.py catalog.py client.py file_access.py schemas.py tools.py README.md install.sh uninstall.sh; do
  cp "$SOURCE_DIR/$file" "$STAGING_DIR/$file"
done
for file in RELEASE-MANIFEST.json DEPENDENCIES.json PROVENANCE.json; do
  if [ -f "$SOURCE_DIR/$file" ]; then
    cp "$SOURCE_DIR/$file" "$STAGING_DIR/$file"
  fi
done
mkdir -p "$STAGING_DIR/skills"
cp -R "$SOURCE_DIR/skills/." "$STAGING_DIR/skills/"

find "$STAGING_DIR" -type d -exec chmod 700 {} \;
find "$STAGING_DIR" -type f -exec chmod 600 {} \;
chmod 700 "$STAGING_DIR/install.sh" "$STAGING_DIR/uninstall.sh"
mv "$STAGING_DIR" "$TARGET_DIR"
trap - EXIT HUP INT TERM

printf '%s\n' "Installed REman Agentic plugin in $TARGET_DIR"
printf '%s\n' "Configure REMAN_AGENT_BASE_URL and REMAN_AGENT_TOKEN, then run: hermes plugins enable reman-agentic"
