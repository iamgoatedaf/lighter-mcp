# Guarded live-order example

This is the canonical "happy path" for a single live trade. **Read
[`DISCLAIMER.md`](../DISCLAIMER.md) first.**

## Setup

```toml
# ~/.lighter/lighter-mcp/config.toml
mode = "live"
kit_path = "/path/to/lighter-agent-kit"
audit_log = "~/.lighter/lighter-mcp/audit.jsonl"
host = "https://testnet.zklighter.elliot.ai"   # use mainnet only after testnet works

[live]
enabled = true
allowed_symbols = ["BTC"]
max_order_notional_usd = 25
max_daily_notional_usd = 100
max_leverage = 3
require_confirmation = true
```

Restart your agent's MCP connection.

## Conversation

> *user*: "Place a $20 long on BTC market."
>
> *agent*: calls `lighter_safety_status`. Reports:
> > Mode `live`, allowlist `[BTC]`, per-order cap $25, daily remaining $100,
> > leverage cap 3x, confirmation required.
>
> *agent*: calls `lighter_live_market_order` with
> `{ "symbol": "BTC", "side": "long", "amount": <derived from $20 / mid price> }`.
> Receives:
>
> ```json
> {
>   "ok": true,
>   "stage": "preview",
>   "tool": "lighter_live_market_order",
>   "plan": {
>     "action": "place_market_order",
>     "symbol": "BTC",
>     "side": "long",
>     "amount": 0.0003,
>     "slippage": 0.01,
>     "estimated_notional_usd": 19.7,
>     "estimated_notional_known": true
>   },
>   "confirmation_id": "9b7c…",
>   "expires_at": 1761234.0
> }
> ```
>
> *agent* (to user): reads back the plan verbatim. "I'm about to place a live
> long market order: 0.0003 BTC, ~$19.7 notional, 1% slippage budget. Confirm?"
>
> *user*: "yes"
>
> *agent*: re-calls `lighter_live_market_order` with the **same** arguments
> plus `confirmation_id = "9b7c…"`. The kit signs and submits the order. The
> response is the kit's structured fill report; the daily-notional counter
> ticks forward automatically.

## Recovery patterns

- If the second call fails with `category: "confirmation"`, the token expired
  or the args drifted. Start over without `confirmation_id`.
- If the second call fails with `category: "safety"`, you crossed a daily
  cap or leverage cap during the preview-to-execute gap. Surface the
  message and ask the user how to proceed.
- For `close_all` the kit's own `--preview` is folded into the `plan` block,
  so the agent always shows position-by-position effects before confirming.
