# Funding-rate scan example

A read-only walkthrough that does not need credentials. Shows how an agent
can pull global funding context.

## Setup

```toml
# ~/.lighter/lighter-mcp/config.toml
mode = "readonly"
kit_path = "/path/to/lighter-agent-kit"
```

## Conversation

> *user*: "Scan all perp markets and tell me the top 5 by absolute funding rate."
>
> *agent*:
>   1. `lighter_list_markets` with `market_type = "perp"` → list of perp symbols.
>   2. For each (or in one shot) `lighter_market_stats` → returns funding rate
>      data for every market.
>   3. Sort by `|funding_rate|` and return the top 5 with current prices.
>
> *user*: "Place a 0.01 ETH paper short on the highest-funding name to fade it."
>
> *agent* (after switching to `mode = "paper"` if not already): `lighter_paper_init`,
> then `lighter_paper_market_order` with `side = "short"`, `amount = 0.01`,
> `symbol = "<top funding symbol>"`.

A future release will add a one-shot `lighter_funding_scan` tool so the agent
doesn't have to fan out manually. For now, the read-only composition above
works on every supported agent.
