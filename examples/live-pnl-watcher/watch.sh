#!/usr/bin/env bash
# Launcher for watch.py. Resolves the lighter-agent-kit path so the SDK
# is importable without polluting global Python.
#
# Resolution order:
#   1. $LIGHTER_KIT_PATH (env)
#   2. kit_path = "..." in ~/.lighter/lighter-mcp/config.toml
#   3. fail with a helpful message
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

resolve_kit_path() {
    if [[ -n "${LIGHTER_KIT_PATH:-}" ]]; then
        printf '%s' "$LIGHTER_KIT_PATH"
        return 0
    fi
    local config="$HOME/.lighter/lighter-mcp/config.toml"
    if [[ -f "$config" ]]; then
        local kp
        kp=$(grep -E '^[[:space:]]*kit_path[[:space:]]*=' "$config" \
            | head -1 \
            | sed -E 's/^[[:space:]]*kit_path[[:space:]]*=[[:space:]]*"?([^"#]*)"?.*$/\1/' \
            | sed -E 's/[[:space:]]+$//')
        if [[ -n "$kp" ]]; then
            # expand a leading ~ if present
            printf '%s' "${kp/#\~/$HOME}"
            return 0
        fi
    fi
    return 1
}

if ! KIT_PATH=$(resolve_kit_path); then
    cat >&2 <<'EOF'
Could not locate a lighter-agent-kit checkout.

Set LIGHTER_KIT_PATH explicitly:
    export LIGHTER_KIT_PATH=/path/to/lighter-agent-kit
    ./watch.sh

Or run `lighter-mcp init` which will create the kit checkout and
populate ~/.lighter/lighter-mcp/config.toml automatically.
EOF
    exit 2
fi

KIT_PYTHON="$KIT_PATH/.venv/bin/python"
if [[ ! -x "$KIT_PYTHON" ]]; then
    echo "kit python not found at $KIT_PYTHON" >&2
    echo "Run the kit's install.sh to create its venv." >&2
    exit 2
fi

exec "$KIT_PYTHON" "$SCRIPT_DIR/watch.py" "$@"
