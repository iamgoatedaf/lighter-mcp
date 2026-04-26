---
name: lighter
description: Trade on Lighter via the lighter MCP server. Use lighter_* tools for market data, paper trading, and gated live trading with two-step confirmations.
---

# Lighter trading skill (Codex)

The `lighter` MCP server is registered. Tool names are `lighter_*` and grouped
by risk family. The full safety contract lives in `adapters/cursor/rules/lighter-safety.mdc`
and is summarized below; behavior must match across agents.

## Always

1. Read `lighter_safety_status` before any non-trivial action; surface the
   active mode and remaining daily notional to the user.
2. For `lighter_live_*` and `lighter_funds_*`: first call returns a preview
   plus `confirmation_id`. Show the entire plan to the user verbatim, ask
   for explicit confirmation, then call again with the same arguments plus
   the issued `confirmation_id`.
3. If a tool returns `category: "safety"` or `category: "confirmation"`,
   surface the error verbatim. Never retry with altered arguments to
   circumvent a gate.
4. Resolve ambiguous symbols with `lighter_list_markets`.

## Never

- Invent or share a confirmation_id with the user.
- Re-execute after a partial failure without re-previewing.
- Bypass `safety` errors by tweaking notional or leverage.
