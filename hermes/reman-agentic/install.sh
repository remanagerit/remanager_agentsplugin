#!/bin/sh
set -eu

umask 077
SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
HERMES_ROOT=${HERMES_HOME:-"$HOME/.hermes"}
PLUGINS_DIR="$HERMES_ROOT/plugins"
TARGET_DIR="$PLUGINS_DIR/reman-agentic"
STAGING_DIR="$PLUGINS_DIR/.reman-agentic-install-$$"
BACKUP_DIR="$PLUGINS_DIR/.reman-agentic-backup-$$"
MODE=install
RESTORE_BACKUP=0

if [ "${1:-}" = "--upgrade" ]; then
  MODE=upgrade
  shift
fi
if [ "$#" -ne 0 ]; then
  printf '%s\n' "Usage: ./install.sh [--upgrade]" >&2
  exit 1
fi

cleanup() {
  rm -rf -- "$STAGING_DIR"
  if [ "$RESTORE_BACKUP" -eq 1 ] && [ -d "$BACKUP_DIR" ] && [ ! -e "$TARGET_DIR" ] && [ ! -L "$TARGET_DIR" ]; then
    mv -- "$BACKUP_DIR" "$TARGET_DIR"
  fi
}
trap cleanup EXIT HUP INT TERM

if [ "$MODE" = "install" ] && { [ -e "$TARGET_DIR" ] || [ -L "$TARGET_DIR" ]; }; then
  printf '%s\n' "Existing Hermes plugin found: $TARGET_DIR" >&2
  printf '%s\n' "Use ./install.sh --upgrade from the verified new release, then restart Hermes." >&2
  exit 1
fi
if [ "$MODE" = "upgrade" ]; then
  if [ -L "$TARGET_DIR" ] || [ ! -d "$TARGET_DIR" ]; then
    printf '%s\n' "Refusing to upgrade a missing, non-directory or symlink plugin target: $TARGET_DIR" >&2
    exit 1
  fi
  if ! grep -q '^name: reman-agentic$' "$TARGET_DIR/plugin.yaml" 2>/dev/null; then
    printf '%s\n' "Refusing to replace an unrecognized plugin directory: $TARGET_DIR" >&2
    exit 1
  fi
fi

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
if [ "$MODE" = "upgrade" ]; then
  mv -- "$TARGET_DIR" "$BACKUP_DIR"
  RESTORE_BACKUP=1
  mv -- "$STAGING_DIR" "$TARGET_DIR"
  RESTORE_BACKUP=0
  rm -rf -- "$BACKUP_DIR"
else
  mv -- "$STAGING_DIR" "$TARGET_DIR"
fi
trap - EXIT HUP INT TERM

printf '%s\n' "Installed REman Agentic plugin 1.2.2 in $TARGET_DIR"
printf '%s\n' "Production URL https://app.remanager.it is built in. Configure REMAN_AGENT_TOKEN."
printf '%s\n' "Use REMAN_AGENT_BASE_URL only to override production with a user-approved staging or self-hosted origin."
printf '%s\n' "For PDF workflows, set REMAN_AGENT_ALLOWED_PDF_DIRS to absolute local directories explicitly approved by the user."
printf '%s\n' "Then run: hermes plugins enable reman-agentic"
printf '%s\n' "Restart Hermes and verify plugin.yaml reports version 1.2.2 before using the connector."
