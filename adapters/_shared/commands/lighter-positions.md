---
name: lighter-positions
description: Show current Lighter positions with size, entry, mark, unrealized PnL, and rough liq distance.
---

# /lighter-positions

Read-only. Do not modify any orders.

Steps:

1. Call `lighter_account_info` to get current positions and account equity.
2. For each non-zero position, call `lighter_market_stats` for the matching
   symbol to grab the current mark/index price (one call per symbol).
3. For each position, compute and display:
    - symbol, side (long/short), size (base), notional (USD),
    - entry price, current mark, unrealized PnL (USD and %),
    - approximate distance to liquidation as a percentage move (use the
      account margin info if available; otherwise mark this field as
      "unknown" — never invent a number).
4. End with totals: aggregate notional and aggregate unrealized PnL.

If there are no open positions, say so in one line and stop.

Never call `lighter_live_*` or `lighter_funds_*` from this command.
