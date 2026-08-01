#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
HERMES="$ROOT/hermes/reman-agentic"
TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/reman-hermes-release.XXXXXX")
cleanup() {
  rm -rf -- "$TEMP_ROOT"
}
trap cleanup EXIT HUP INT TERM

(cd "$ROOT" && python3 -m unittest hermes/reman-agentic/tests/test_connector.py)
python3 -m py_compile "$HERMES/__init__.py" "$HERMES/catalog.py" "$HERMES/client.py" "$HERMES/file_access.py" "$HERMES/schemas.py" "$HERMES/tools.py"
sh -n "$HERMES/install.sh" "$HERMES/uninstall.sh"

DIRTY_ARG=
if [ "${REMAN_HERMES_ALLOW_DIRTY_CANDIDATE:-0}" = "1" ]; then
  DIRTY_ARG=--allow-dirty
fi
python3 "$ROOT/scripts/build-hermes-candidate.py" --output "$TEMP_ROOT/release" $DIRTY_ARG > "$TEMP_ROOT/build.json"
ARCHIVE=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["archive"])' "$TEMP_ROOT/build.json")
mkdir -p "$TEMP_ROOT/unpacked"
tar -xzf "$ARCHIVE" -C "$TEMP_ROOT/unpacked"

HERMES_HOME="$TEMP_ROOT/hermes-home" "$TEMP_ROOT/unpacked/reman-agentic/install.sh"
INSTALLED="$TEMP_ROOT/hermes-home/plugins/reman-agentic"
printf '%s\n' "stale" > "$INSTALLED/stale-version-marker"
HERMES_HOME="$TEMP_ROOT/hermes-home" "$TEMP_ROOT/unpacked/reman-agentic/install.sh" --upgrade
test ! -e "$INSTALLED/stale-version-marker"
grep -q '^version: 1.2.2$' "$INSTALLED/plugin.yaml"
python3 - "$INSTALLED" <<'PY'
import importlib.util
import sys
from pathlib import Path

plugin_dir = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location(
    "reman_candidate_plugin", plugin_dir / "__init__.py", submodule_search_locations=[str(plugin_dir)]
)
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)
tools = []

class Context:
    def register_tool(self, **definition):
        tools.append(definition["name"])

    def register_skill(self, **definition):
        assert Path(definition["path"]).is_file()

plugin.register(Context())
expected = {
    "reman_available_tools",
    "reman_accounting_tool_contract",
    "reman_accounting_read",
    "reman_accounting_prepare_action",
    "reman_accounting_prepare_file_action",
    "reman_accounting_list_companies",
    "reman_accounting_search_partners",
    "reman_accounting_search_non_electronic_invoices",
    "reman_accounting_create_non_electronic_invoice",
}
assert set(tools) == expected, tools
assert not any(word in name for name in tools for word in ("upload", "delete", "direct", "mcp"))
PY
HERMES_HOME="$TEMP_ROOT/hermes-home" "$INSTALLED/uninstall.sh"
test ! -e "$INSTALLED"

printf '%s\n' "Hermes release gate passed with a clean synthetic install/uninstall."
