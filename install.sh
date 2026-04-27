#!/usr/bin/env bash
# Lighter MCP installer (legacy shim).
#
# Modern users should run one of these instead — they're all faster and don't
# require a git checkout:
#
#     pipx install lighter-mcp && lighter-mcp init       # recommended
#     uvx lighter-mcp init                               # ephemeral, no install
#
# (Homebrew and Smithery installs are tracked in ROADMAP.md under v0.2.)
#
# This script is kept for two reasons:
#
#   1. Backwards compatibility with anyone whose docs / muscle memory still
#      says ``bash install.sh``.
#   2. Source-checkout development: from a fresh ``git clone`` it gets you to
#      a working ``lighter-mcp`` binary without globally installing the
#      package, so contributors can iterate locally.
#
# Either way it ends up calling ``lighter-mcp init``, so the heavy lifting
# (kit auto-clone, agent detection, config writing) happens in one place.
#
# Usage:
#     bash install.sh                           # editable install + init (no agents wired)
#     bash install.sh --adapter cursor          # also wire the Cursor adapter
#     bash install.sh --kit-path /path/to/kit   # use an existing kit checkout
#     bash install.sh --mode paper              # initial mode in the generated config
#     bash install.sh --no-doctor               # skip the smoke check
#
# All flags are forwarded to ``lighter-mcp init``; this script is a 30-line
# shim, not a config writer.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_ROOT="${LIGHTER_MCP_INSTALL_ROOT:-$HOME/.lighter/lighter-mcp}"
VENV_DIR="$INSTALL_ROOT/venv"

# Forwarded init flags
INIT_ARGS=()
ADAPTER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --adapter)        ADAPTER="$2"; shift 2 ;;
    --kit-path)       INIT_ARGS+=("--kit-path" "$2"); shift 2 ;;
    --mode)           INIT_ARGS+=("--mode" "$2"); shift 2 ;;
    --install-root)   INSTALL_ROOT="$2"; VENV_DIR="$INSTALL_ROOT/venv";
                      INIT_ARGS+=("--install-root" "$2"); shift 2 ;;
    --no-doctor)      INIT_ARGS+=("--no-doctor"); shift ;;
    --no-scaffolds)   INIT_ARGS+=("--no-scaffolds"); shift ;;
    --force)          INIT_ARGS+=("--force"); shift ;;
    -h|--help)
      sed -n '2,33p' "$0"
      exit 0
      ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

if [[ -n "$ADAPTER" ]]; then
  case "$ADAPTER" in
    cursor|claude|claude-desktop|codex)
      INIT_ARGS+=("--agents" "${ADAPTER/claude/claude-code}")
      ;;
    openclaw|generic)
      echo "→ adapter '$ADAPTER' has no auto-install path; see adapters/$ADAPTER/README.md" >&2
      ;;
    *) echo "✗ unknown adapter: $ADAPTER" >&2; exit 2 ;;
  esac
fi

# Pick a Python — same logic as before, just shorter.
find_python() {
  for c in python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1; then
      ver=$("$c" -c 'import sys; print(sys.version_info[:2])')
      [[ "$ver" == "(3, 1"* ]] && { echo "$c"; return 0; }
    fi
  done
  return 1
}
PYTHON_BIN="$(find_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "✗ Python 3.10+ required (try: brew install python@3.12)" >&2
  exit 2
fi

mkdir -p "$INSTALL_ROOT"
if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade --quiet pip
"$VENV_DIR/bin/pip" install --quiet -e "$SCRIPT_DIR"

echo "→ installed lighter-mcp into $VENV_DIR"
echo "→ running: lighter-mcp init ${INIT_ARGS[*]:-}"
exec "$VENV_DIR/bin/lighter-mcp" init ${INIT_ARGS[@]+"${INIT_ARGS[@]}"}
