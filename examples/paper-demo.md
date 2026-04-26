# Paper trading demo

Walks through the smallest end-to-end flow that exercises the MCP server
without any risk of real funds moving.

## Setup

```bash
# In ~/.lighter/lighter-mcp/config.toml:
mode = "paper"
kit_path = "/path/to/lighter-agent-kit"
```

Restart your agent's MCP connection.

## Conversation

> *agent*: `lighter_safety_status` → confirms `mode = "paper"`.
> *agent*: `lighter_paper_init` → creates a fresh paper account.
> *user*: "go long 0.01 BTC at market"
> *agent*: `lighter_paper_market_order` with `symbol = "BTC"`, `side = "long"`,
> `amount = 0.01`. Returns the simulated fills.
> *user*: "show my position"
> *agent*: `lighter_paper_positions` → returns the open BTC position with
> entry price, mark price, unrealized PnL, and liquidation price.
> *user*: "what would my liquidation price be?"
> *agent*: `lighter_paper_liquidation_price` with `symbol = "BTC"` → returns
> the same number from a different angle for sanity-checking.

Reset between runs:

> *user*: "wipe paper state"
> *agent*: `lighter_paper_reset`.
