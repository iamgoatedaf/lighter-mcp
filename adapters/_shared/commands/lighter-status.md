---
name: lighter-status
description: One-glance snapshot of the Lighter account — mode, safety budget, balance, open orders.
---

# /lighter-status

You are answering a Lighter status request. Do **not** trade. Read-only.

Steps:

1. Call `lighter_safety_status`. Note the active mode, allowed symbols, daily
   notional used vs cap, and whether confirmation is required.
2. Call `lighter_account_info` for balances and equity.
3. Call `lighter_orders_open` (no symbol filter) for currently resting orders.
4. Render a compact summary in this order:
    - Mode and remaining daily notional budget.
    - Account equity and free collateral.
    - Open orders grouped by symbol with side, size, price, and time-in-force
      if present.
    - Any safety warnings the snapshot returned (e.g. cap exhausted).

Keep the answer to ~10 lines unless the user asks for more detail. Use a
plain table or bullet list — no preamble like "here is your status".
