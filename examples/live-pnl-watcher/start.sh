#!/usr/bin/env bash
# Open two Terminal.app windows: one runs the live PnL watcher, the
# other is a prompt for trade.sh commands. macOS only.
#
# On non-macOS, just open two terminals manually:
#     window 1: ./watch.sh
#     window 2: ./trade.sh status
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ "$(uname)" != "Darwin" ]]; then
    cat <<EOF
This launcher uses AppleScript and only works on macOS.

Open two terminals manually and run:
    window 1:  $DIR/watch.sh
    window 2:  $DIR/trade.sh status
EOF
    exit 1
fi

osascript <<EOF
tell application "Terminal"
    activate
    do script "echo 'Watcher window — connecting to Lighter WS...'; sleep 1; \"$DIR/watch.sh\""
    do script "echo 'Trade window. Try:'; echo '  $DIR/trade.sh status'; echo '  $DIR/trade.sh long SOL 50'; echo '  $DIR/trade.sh short BTC 0.001'; echo '  $DIR/trade.sh raw reset --collateral 1000000 --tier premium_7'; echo ''"
end tell
EOF
