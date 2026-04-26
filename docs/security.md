# Security

See [`SECURITY.md`](../SECURITY.md) for the threat model and reporting
guidance. Operational notes:

## Mode promotion checklist

Before flipping `mode` from `paper` to `live`:

1. Run `lighter-mcp doctor` and confirm `system.status = 200`.
2. Confirm `auth.status` shows credentials present **only** for the
   account index you intend to trade.
3. Set `live.allowed_symbols`, `live.max_order_notional_usd`,
   `live.max_daily_notional_usd`, `live.max_leverage` to the narrowest
   reasonable values for the session.
4. Keep `live.require_confirmation = true`.
5. Restart the MCP transport.

Before flipping `mode = "funds"`:

1. Re-do the live checklist.
2. Set `funds.max_withdrawal_usd` to a sensible cap.
3. Decide whether you actually need transfers; if not, leave
   `funds.transfers_enabled = false`.

## Audit log review

The audit file is `~/.lighter/lighter-mcp/audit.jsonl`. Useful queries:

```bash
# All live writes today
jq 'select(.tool|startswith("lighter_live_"))' \
   ~/.lighter/lighter-mcp/audit.jsonl

# Anything that returned an error envelope
jq 'select(.ok==false)' ~/.lighter/lighter-mcp/audit.jsonl

# Today's totaled paper trade volume
jq -r 'select(.tool|startswith("lighter_paper_")) | .ts' \
   ~/.lighter/lighter-mcp/audit.jsonl | wc -l
```

## Key rotation

If anything looks off, rotate API keys via the kit's flow and revoke the
previous key on Lighter. The MCP server picks up the new key on next
subprocess invocation; no MCP restart is required.
