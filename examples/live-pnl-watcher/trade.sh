#!/usr/bin/env bash
# Ergonomic wrapper around the kit's scripts/paper.py.
#
# Examples:
#     ./trade.sh long  SOL 50
#     ./trade.sh short BTC 0.01
#     ./trade.sh sell  SOL 25
#     ./trade.sh buy   BTC 0.001
#     ./trade.sh status
#     ./trade.sh positions
#     ./trade.sh trades
#     ./trade.sh health
#     ./trade.sh raw   order limit SOL --side buy --amount 50 --price 80
#     ./trade.sh raw   reset --collateral 1000000 --tier premium_7
#
# When run alongside watch.sh, the watcher auto-detects state changes
# via mtime, so positions update without restarting the watcher.
#
# Resolution order for the kit path: $LIGHTER_KIT_PATH, then kit_path in
# ~/.lighter/lighter-mcp/config.toml. See watch.sh for details.
set -euo pipefail

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
            printf '%s' "${kp/#\~/$HOME}"
            return 0
        fi
    fi
    return 1
}

usage() {
    sed -n '2,18p' "$0"
}

if ! KIT=$(resolve_kit_path); then
    echo "Could not locate lighter-agent-kit. Set LIGHTER_KIT_PATH or run \`lighter-mcp init\`." >&2
    exit 2
fi

PY="$KIT/.venv/bin/python"
PAPER="$KIT/scripts/paper.py"

if [[ ! -x "$PY" ]]; then
    echo "kit python not found: $PY" >&2
    exit 2
fi
if [[ ! -f "$PAPER" ]]; then
    echo "kit paper.py not found: $PAPER" >&2
    exit 2
fi

cmd="${1:-}"
shift || true

case "$cmd" in
    buy|long)
        [[ $# -lt 2 ]] && { echo "usage: $0 $cmd SYMBOL AMOUNT" >&2; exit 2; }
        exec "$PY" "$PAPER" order market "$1" --side buy --amount "$2"
        ;;
    sell|short)
        [[ $# -lt 2 ]] && { echo "usage: $0 $cmd SYMBOL AMOUNT" >&2; exit 2; }
        exec "$PY" "$PAPER" order market "$1" --side sell --amount "$2"
        ;;
    status|positions|trades|health)
        exec "$PY" "$PAPER" "$cmd" "$@"
        ;;
    raw)
        exec "$PY" "$PAPER" "$@"
        ;;
    ""|-h|--help)
        usage
        exit 0
        ;;
    *)
        echo "unknown command: $cmd" >&2
        usage
        exit 2
        ;;
esac
