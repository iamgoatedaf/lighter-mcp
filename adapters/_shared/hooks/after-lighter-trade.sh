#!/usr/bin/env bash
# Posted after a successful lighter_live_* or lighter_funds_* tool call.
#
# The hook receives the tool name, args (sanitized), and result via stdin
# as a single JSON line. It writes a one-line summary to a local
# notifications file and (best-effort) emits a desktop notification on
# macOS via osascript.
#
# Wire it up:
#   - Cursor:     hooks.json  → post-tool-call event matching `lighter_(live|funds)_*`
#   - Claude Code: .claude/hooks/post-tool-call.sh
#   - Codex:       .codex-plugin/plugin.json → hooks.post_tool_call
#
# This script must remain side-effect-light; never re-call the MCP server
# from here (avoids recursive audit storms).

set -euo pipefail

NOTIFY_LOG="${LIGHTER_HOOK_LOG:-$HOME/.lighter/lighter-mcp/notifications.log}"
mkdir -p "$(dirname "$NOTIFY_LOG")"

# Read the event payload (one JSON line on stdin). Fall back to empty.
PAYLOAD="$(cat 2>/dev/null || echo '{}')"

LINE=$(python3 - <<PY
import json, sys, time
raw = """$PAYLOAD"""
try:
    p = json.loads(raw or "{}")
except Exception:
    p = {}
tool = p.get("tool") or p.get("name") or "lighter_unknown"
args = p.get("args") or p.get("arguments") or {}
res  = p.get("result") or {}
ok   = p.get("ok", True if "error" not in (res if isinstance(res, dict) else {}) else False)
sym  = args.get("input", {}).get("symbol") if isinstance(args.get("input"), dict) else args.get("symbol")
amt  = args.get("input", {}).get("amount") if isinstance(args.get("input"), dict) else args.get("amount")
ts   = time.strftime("%Y-%m-%dT%H:%M:%S")
print(f"{ts} {tool} ok={ok} symbol={sym} amount={amt}")
PY
)

echo "$LINE" >> "$NOTIFY_LOG"

if [[ "$(uname -s)" == "Darwin" ]] && command -v osascript >/dev/null 2>&1; then
    osascript -e "display notification \"$LINE\" with title \"Lighter MCP\"" >/dev/null 2>&1 || true
fi
