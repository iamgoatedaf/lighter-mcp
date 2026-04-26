#!/usr/bin/env bash
# Lighter MCP installer.
#
# Detects Python 3.11+, creates a virtualenv for the MCP server, installs the
# lighter-mcp package in editable mode, drops a default readonly config under
# ~/.lighter/lighter-mcp/, and runs a smoke check.
#
# Usage:
#     bash install.sh                          # install with prompts
#     bash install.sh --kit-path /path/to/kit  # non-interactive
#     bash install.sh --mode paper             # initial mode (default: readonly)
#     bash install.sh --no-doctor              # skip the smoke check at the end
#     bash install.sh --adapter cursor         # also install Cursor scaffolds
#                                              #   (commands/agents/rules/hook)
#                                              # supported: cursor | claude | codex |
#                                              #            openclaw | claude-desktop |
#                                              #            generic
#
# The installer NEVER touches your live mode flags; live trading and fund
# movements remain off until you edit the config explicitly.

set -euo pipefail

# ----------------------------------------------------------------------------
# Args
# ----------------------------------------------------------------------------
KIT_PATH=""
MODE="readonly"
RUN_DOCTOR=true
INSTALL_ROOT="${LIGHTER_MCP_INSTALL_ROOT:-$HOME/.lighter/lighter-mcp}"
ADAPTER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --kit-path) KIT_PATH="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --install-root) INSTALL_ROOT="$2"; shift 2 ;;
    --no-doctor) RUN_DOCTOR=false; shift ;;
    --adapter) ADAPTER="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

case "$MODE" in
  readonly|paper|live|funds) ;;
  *) echo "invalid --mode: $MODE (expected: readonly|paper|live|funds)" >&2; exit 2 ;;
esac

# ----------------------------------------------------------------------------
# Locate sources
# ----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "→ lighter-mcp sources: $SCRIPT_DIR"

if [[ -z "$KIT_PATH" ]]; then
  if [[ -d "$SCRIPT_DIR/../lighter-agent-kit" ]]; then
    KIT_PATH="$(cd "$SCRIPT_DIR/../lighter-agent-kit" && pwd)"
  fi
fi

if [[ -z "$KIT_PATH" ]]; then
  echo "✗ lighter-agent-kit path not provided and ../lighter-agent-kit not found." >&2
  echo "  Install it first with:" >&2
  echo "    curl -fsSL https://github.com/elliottech/lighter-agent-kit/releases/latest/download/install.sh | bash" >&2
  echo "  Then re-run this installer with --kit-path /path/to/lighter-agent-kit." >&2
  exit 2
fi
if [[ ! -d "$KIT_PATH" ]]; then
  echo "✗ kit path does not exist: $KIT_PATH" >&2
  exit 2
fi
echo "→ lighter-agent-kit:    $KIT_PATH"

# ----------------------------------------------------------------------------
# Python detection
# ----------------------------------------------------------------------------
find_python() {
  for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      version=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
      major=${version%.*}
      minor=${version#*.}
      if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
        echo "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

PYTHON_BIN="$(find_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "✗ Python 3.10+ is required but was not found on PATH." >&2
  echo "  On macOS:  brew install python@3.11" >&2
  echo "  On Linux:  use your distro package manager (python3.11)" >&2
  exit 2
fi
PYTHON_PATH="$(command -v "$PYTHON_BIN")"
echo "→ Python:               $PYTHON_PATH ($($PYTHON_BIN -c 'import sys; print(sys.version.split()[0])'))"

# ----------------------------------------------------------------------------
# Virtualenv
# ----------------------------------------------------------------------------
VENV_DIR="$INSTALL_ROOT/venv"
mkdir -p "$INSTALL_ROOT"
echo "→ install root:         $INSTALL_ROOT"

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PY="$VENV_DIR/bin/python"
"$VENV_PY" -m pip install --upgrade pip --quiet
"$VENV_PY" -m pip install --quiet -e "$SCRIPT_DIR"
echo "→ installed lighter-mcp into $VENV_DIR"

# ----------------------------------------------------------------------------
# Default config
# ----------------------------------------------------------------------------
CONFIG_PATH="$INSTALL_ROOT/config.toml"
if [[ ! -f "$CONFIG_PATH" ]]; then
  template="$SCRIPT_DIR/configs/lighter-mcp.${MODE}.toml"
  if [[ ! -f "$template" ]]; then
    template="$SCRIPT_DIR/configs/lighter-mcp.readonly.toml"
  fi
  # Substitute kit_path via Python (tomllib roundtrip is overkill for a single
  # field, but we use python's repr to safely escape backslashes/quotes that
  # would otherwise produce a syntactically broken TOML or even allow
  # injection of extra keys via crafted paths).
  TEMPLATE="$template" CONFIG_PATH="$CONFIG_PATH" KIT_PATH="$KIT_PATH" \
    "$VENV_PY" - <<'PY'
import os, re
src = open(os.environ["TEMPLATE"]).read()
kit = os.environ["KIT_PATH"]
# TOML basic-string: escape backslash and double-quote.
escaped = kit.replace("\\", "\\\\").replace("\"", "\\\"")
new = re.sub(
    r'^kit_path\s*=\s*".*"',
    f'kit_path = "{escaped}"',
    src,
    count=1,
    flags=re.MULTILINE,
)
open(os.environ["CONFIG_PATH"], "w").write(new)
PY
  echo "→ wrote config:         $CONFIG_PATH"
else
  echo "→ existing config kept: $CONFIG_PATH"
fi

# ----------------------------------------------------------------------------
# Adapter scaffolds
# ----------------------------------------------------------------------------
install_cursor() {
  local target="${INSTALL_ADAPTER_TARGET:-$PWD}"
  echo "→ installing Cursor adapter into $target/.cursor/"
  mkdir -p "$target/.cursor/rules" "$target/.cursor/commands" "$target/.cursor/agents"
  cp "$SCRIPT_DIR/adapters/cursor/mcp.example.json" "$target/.cursor/mcp.json"
  cp "$SCRIPT_DIR/adapters/cursor/hooks.json"        "$target/.cursor/hooks.json"
  cp "$SCRIPT_DIR/adapters/cursor/rules/lighter-safety.mdc" "$target/.cursor/rules/"
  cp "$SCRIPT_DIR"/adapters/_shared/commands/*.md    "$target/.cursor/commands/"
  cp "$SCRIPT_DIR"/adapters/_shared/agents/*.md      "$target/.cursor/agents/"
  echo "  ✓ rules, 5 slash-commands, lighter-trader sub-agent, after-trade hook"
}

install_claude_code() {
  local target="${INSTALL_ADAPTER_TARGET:-$PWD}"
  echo "→ installing Claude Code adapter into $target/.claude/"
  mkdir -p "$target/.claude/commands" "$target/.claude/agents" "$target/.claude/hooks"
  cp "$SCRIPT_DIR/adapters/claude/claude_code_config.example.json" "$target/.claude/mcp.json"
  cp "$SCRIPT_DIR"/adapters/_shared/commands/*.md "$target/.claude/commands/"
  cp "$SCRIPT_DIR"/adapters/_shared/agents/*.md   "$target/.claude/agents/"
  cp "$SCRIPT_DIR/adapters/_shared/hooks/after-lighter-trade.sh" \
     "$target/.claude/hooks/post-tool-call.sh"
  chmod +x "$target/.claude/hooks/post-tool-call.sh"
  echo "  ✓ 5 slash-commands, lighter-trader sub-agent, post-tool-call hook"
}

install_codex() {
  local target="${INSTALL_ADAPTER_TARGET:-$HOME/.codex/plugins/lighter}"
  echo "→ installing Codex plugin into $target/"
  mkdir -p "$target"
  cp -R "$SCRIPT_DIR/adapters/codex/.codex-plugin/." "$target/"
  cp    "$SCRIPT_DIR/adapters/codex/.mcp.json"       "$target/.mcp.json"
  cp -R "$SCRIPT_DIR/adapters/codex/skills"          "$target/skills"
  echo "  ✓ MCP, SKILL, 5 commands, sub-agent, post-tool-call hook"
}

if [[ -n "$ADAPTER" ]]; then
  case "$ADAPTER" in
    cursor)   install_cursor ;;
    claude)   install_claude_code ;;
    codex)    install_codex ;;
    openclaw|generic|claude-desktop)
      echo "→ adapter selected:     $ADAPTER"
      echo "  Manual install — see $SCRIPT_DIR/adapters/$ADAPTER/README.md."
      ;;
    *) echo "✗ unknown adapter: $ADAPTER" >&2; exit 2 ;;
  esac
fi

# ----------------------------------------------------------------------------
# Doctor smoke check
# ----------------------------------------------------------------------------
if $RUN_DOCTOR; then
  echo "→ running smoke check…"
  LIGHTER_MCP_CONFIG="$CONFIG_PATH" "$VENV_DIR/bin/lighter-mcp" doctor || {
    echo "✗ doctor failed; review the JSON above for details." >&2
    exit 1
  }
fi

cat <<EOF

✓ lighter-mcp installed.

Console command:  $VENV_DIR/bin/lighter-mcp
Config:           $CONFIG_PATH
Audit log:        $INSTALL_ROOT/audit.jsonl

Next steps:
  1. Install an adapter:
       bash install.sh --adapter cursor    # rules + 5 slash-commands +
                                           #   lighter-trader sub-agent + hook
       bash install.sh --adapter claude    # same set for Claude Code
       bash install.sh --adapter codex     # full Codex plugin
  2. Update config to switch modes (readonly → paper → live → funds).
  3. Re-run \`$VENV_DIR/bin/lighter-mcp doctor\` after every config change.

Once an adapter is installed, try in your agent:
  /lighter-status        — account snapshot
  /lighter-positions     — positions with PnL and liq distance
  /lighter-paper         — switch to paper mode
  /lighter-audit         — recent audit log entries
  /lighter-kill          — panic close (cancel_all + close_all, two-step)

For live trading: read DISCLAIMER.md and SECURITY.md first.
EOF
