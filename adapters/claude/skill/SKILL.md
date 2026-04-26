---
name: lighter
description: Trade on Lighter via the lighter MCP server. Includes read-only market data, paper trading, and gated live trading with two-step confirmations.
---

# Lighter trading skill

You have access to the `lighter` MCP server. Tools are namespaced
`lighter_*` and grouped by risk:

| Family             | Effect                                       |
| ------------------ | -------------------------------------------- |
| `lighter_market_*` | Public market reads.                         |
| `lighter_account_*`| Authenticated reads using local credentials. |
| `lighter_paper_*`  | Local simulation; no real funds move.        |
| `lighter_live_*`   | Real exchange writes; gated and audited.     |
| `lighter_funds_*`  | Transfers and withdrawals; strictest gates.  |

Always:

1. Call `lighter_safety_status` before a non-trivial action and report the
   active mode plus any caps (allowed symbols, daily notional, leverage).
2. For any `lighter_live_*` or `lighter_funds_*` tool: call once without
   `confirmation_id` to get a `preview` and `confirmation_id`. Read the plan
   back to the user verbatim and ask "yes to execute". Only on explicit
   confirmation, repeat the call with the same args plus the id.
3. If a tool returns `category: "safety"` or `category: "confirmation"`, do
   not bypass it. Surface the message to the user and ask how to proceed.
4. Use `lighter_list_markets` to resolve ambiguous symbols. Do not guess
   market_index or symbol naming.

Never:

- Invent or share a `confirmation_id`. Tokens are bound to args.
- Re-issue a high-risk call after a partial failure without re-previewing.
- Paraphrase the preview's `warning` fields. Read them as-is.

Workflow templates:

- *Place a paper order*: `lighter_paper_init` (once), then
  `lighter_paper_market_order` or `lighter_paper_ioc_order`.
- *Place a live order*: ensure the user is on `mode = live`, run
  `lighter_live_market_order` (preview → confirm → execute).
- *Cancel everything*: `lighter_live_cancel_all` (preview → confirm).
- *Flatten*: `lighter_live_close_all` (kit-side preview is included in the
  envelope plan).
- *Withdraw*: `lighter_funds_withdraw` (preview → confirm).
