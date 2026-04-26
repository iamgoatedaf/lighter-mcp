#!/usr/bin/env bash
# Sync the canonical command/agent/hook prompts under adapters/_shared/
# into each per-platform adapter folder.
#
# Why: by default we ship symlinks from
#   adapters/{cursor,claude}/commands/   → adapters/_shared/commands/
#   adapters/{cursor,claude}/agents/     → adapters/_shared/agents/
#   adapters/codex/.codex-plugin/{commands,agents,hooks}/ → adapters/_shared/...
#
# Symlinks are convenient on macOS / Linux but Windows checkouts (default
# Git for Windows config, no `core.symlinks=true`) materialize them as text
# files containing the relative path. This script replaces those broken
# symlinks with real copies. Re-run any time the canonical prompts under
# adapters/_shared/ change.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SHARED="$REPO_ROOT/adapters/_shared"

copy_tree() {
    local src="$1"
    local dst="$2"
    mkdir -p "$dst"
    # Remove any existing symlinks/files in dst, then copy fresh.
    find "$dst" -maxdepth 1 -mindepth 1 -exec rm -rf {} +
    cp -R "$src"/. "$dst"/
    echo "  ✓ $dst"
}

echo "→ syncing adapters/_shared/ into per-platform folders…"

copy_tree "$SHARED/commands" "$REPO_ROOT/adapters/cursor/commands"
copy_tree "$SHARED/agents"   "$REPO_ROOT/adapters/cursor/agents"

copy_tree "$SHARED/commands" "$REPO_ROOT/adapters/claude/commands"
copy_tree "$SHARED/agents"   "$REPO_ROOT/adapters/claude/agents"

copy_tree "$SHARED/commands" "$REPO_ROOT/adapters/codex/.codex-plugin/commands"
copy_tree "$SHARED/agents"   "$REPO_ROOT/adapters/codex/.codex-plugin/agents"
copy_tree "$SHARED/hooks"    "$REPO_ROOT/adapters/codex/.codex-plugin/hooks"

echo "✓ done. Per-platform adapters now contain real file copies."
