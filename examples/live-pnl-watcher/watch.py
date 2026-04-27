#!/usr/bin/env python3
"""Real-time PnL watcher for Lighter paper positions (WebSocket).

Connects to the Lighter mainnet WebSocket, subscribes to order books for
the markets where you currently hold open paper positions, derives a
live mark price from the mid of the best bid/ask, and re-renders
unrealized PnL on every push from the exchange (~50-200 ms latency).

The local ``paper-state.json`` is reloaded automatically when its mtime
changes, so opening or closing positions through the MCP / kit / CLI is
reflected here without a restart.

Usage:
    ./watch.sh                    # picks default ~/.lighter/lighter-agent-kit/paper-state.json
    ./watch.sh --debug
    ./watch.sh --state /custom/path/paper-state.json
    ./watch.sh --host testnet.zklighter.elliot.ai

Note: Lighter's ``/stream`` WS endpoint is geo-restricted at the
CloudFront edge. From a restricted region the connect handshake returns
HTTP 400 with code 20558. Use a VPN that exits in an allowed
jurisdiction. Some past edge rules also gated requests by User-Agent;
this script pins the SDK's UA on the WS handshake just in case a future
rule starts gating WS as well.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import websockets.sync.client as _ws_sync
import lighter.ws_client as _lighter_ws

_LIGHTER_UA = "OpenAPI-Generator/1.0.0/python"
_orig_connect = _ws_sync.connect


def _connect_with_ua(uri, *args, **kwargs):
    kwargs.setdefault("user_agent_header", _LIGHTER_UA)
    return _orig_connect(uri, *args, **kwargs)


_lighter_ws.connect = _connect_with_ua

import lighter  # noqa: E402

DEFAULT_STATE = Path.home() / ".lighter" / "lighter-agent-kit" / "paper-state.json"
DEFAULT_HOST = "mainnet.zklighter.elliot.ai"  # SDK prepends wss:// itself


def parse_positions(state: dict) -> tuple[list[dict], float]:
    positions: list[dict] = []
    market_configs = state.get("market_configs", {}) or {}
    for mid_str, pos in (state.get("account", {}).get("positions") or {}).items():
        size = float(pos.get("size", 0) or 0)
        if abs(size) < 1e-9:
            continue
        cfg = market_configs.get(mid_str, {}) or {}
        positions.append(
            {
                "market_id": int(mid_str),
                "symbol": cfg.get("symbol", f"M{mid_str}"),
                "size": size,
                "entry": float(pos.get("avg_entry_price", 0) or 0),
            }
        )
    collateral = float((state.get("account") or {}).get("collateral", 0) or 0)
    return positions, collateral


def mid_from_book(book: object) -> Optional[tuple[float, float]]:
    """Return ``(mid, spread_bps)`` from an order-book payload, or None."""
    if not isinstance(book, dict):
        return None
    bids = book.get("bids") or []
    asks = book.get("asks") or []

    def best(levels, op):
        prices: list[float] = []
        for lv in levels:
            p = None
            if isinstance(lv, dict):
                p = lv.get("price")
            elif isinstance(lv, (list, tuple)) and lv:
                p = lv[0]
            try:
                if p is not None:
                    prices.append(float(p))
            except (TypeError, ValueError):
                pass
        return op(prices) if prices else None

    bb = best(bids, max)
    ba = best(asks, min)
    if bb is None or ba is None:
        return None
    mid = (bb + ba) / 2.0
    spread_bps = (ba - bb) / mid * 10_000.0 if mid > 0 else 0.0
    return mid, spread_bps


class Watcher:
    def __init__(self, state_path: Path, debug: bool = False):
        self.state_path = state_path
        self.debug = debug
        self.marks: dict[int, float] = {}
        self.spreads_bps: dict[int, float] = {}
        self.positions: list[dict] = []
        self.collateral: float = 0.0
        self.state_mtime: float = 0.0
        self.last_tick_at: float = time.monotonic()
        self.last_tick_ms: int = 0
        self.tick_count: int = 0
        self.reload_state()

    def reload_state(self) -> None:
        try:
            mt = self.state_path.stat().st_mtime
        except OSError:
            return
        if mt == self.state_mtime:
            return
        try:
            with self.state_path.open() as f:
                state = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        self.state_mtime = mt
        self.positions, self.collateral = parse_positions(state)

    def market_ids(self) -> list[int]:
        return [p["market_id"] for p in self.positions]

    def on_book_update(self, market_id, book) -> None:
        if self.debug:
            kind = type(book).__name__
            keys = list(book.keys())[:6] if isinstance(book, dict) else "n/a"
            print(f"[ws] mid={market_id} type={kind} keys={keys}", flush=True)

        result = mid_from_book(book)
        if result is None:
            return
        mid, spread = result

        try:
            mid_key = int(market_id)
        except (TypeError, ValueError):
            return

        now = time.monotonic()
        self.last_tick_ms = int((now - self.last_tick_at) * 1000)
        self.last_tick_at = now
        self.tick_count += 1
        self.marks[mid_key] = mid
        self.spreads_bps[mid_key] = spread

        self.reload_state()
        self.render()

    def render(self) -> None:
        sys.stdout.write("\033[H\033[2J")  # clear screen + home
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(
            f"=== Lighter Paper PnL — {now}  "
            f"(tick #{self.tick_count}, Δ{self.last_tick_ms:>4}ms) ===\n"
        )

        total = 0.0
        for p in self.positions:
            mark = self.marks.get(p["market_id"])
            spread = self.spreads_bps.get(p["market_id"])
            side = "long " if p["size"] >= 0 else "short"
            if mark is None:
                mark_s, pnl_s, sp_s = "         —", "       —", "    —"
            else:
                pnl = p["size"] * (mark - p["entry"])
                total += pnl
                mark_s = f"${mark:>10,.4f}"
                pnl_s = f"${pnl:>+9,.2f}"
                sp_s = f"{spread:>4.1f}bps" if spread is not None else "    —"
            print(
                f"  {p['symbol']:>4}  {side}  "
                f"size={abs(p['size']):>10.4f}  "
                f"entry=${p['entry']:>11,.4f}  "
                f"mark={mark_s}  "
                f"sp={sp_s}  "
                f"uPnL={pnl_s}"
            )

        print()
        print(f"  Total uPnL:   ${total:+,.4f}")
        print(f"  Collateral:   ${self.collateral:,.2f}")
        print(f"  Equity:       ${self.collateral + total:,.2f}")
        print()
        print("Ctrl+C to exit  •  paper-state auto-reloads on change")
        sys.stdout.flush()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Real-time PnL watcher for Lighter paper positions.",
    )
    ap.add_argument(
        "--state",
        default=str(DEFAULT_STATE),
        help=f"paper-state.json path (default: {DEFAULT_STATE})",
    )
    ap.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"WS host without scheme (default: {DEFAULT_HOST})",
    )
    ap.add_argument(
        "--debug",
        action="store_true",
        help="Print raw WS messages.",
    )
    args = ap.parse_args()

    state_path = Path(args.state).expanduser()
    if not state_path.is_file():
        print(f"paper-state not found at {state_path}", file=sys.stderr)
        print(
            "Initialize the paper account first with `lighter-mcp init` "
            "or `paper.py init`.",
            file=sys.stderr,
        )
        return 2

    watcher = Watcher(state_path, debug=args.debug)
    if not watcher.positions:
        print("No open paper positions; nothing to watch.")
        print("Open one (e.g. `./trade.sh long SOL 1`) and rerun.")
        return 0

    print(f"Connecting to wss://{args.host}/stream ...")
    print(f"Subscribing to markets: {watcher.market_ids()}")
    print(f"Loaded {len(watcher.positions)} position(s) from {state_path}")
    print()

    client = lighter.WsClient(
        host=args.host,
        order_book_ids=watcher.market_ids(),
        account_ids=[],
        on_order_book_update=watcher.on_book_update,
        on_account_update=lambda *a, **k: None,
    )

    try:
        client.run()
    except KeyboardInterrupt:
        print("\nbye")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
