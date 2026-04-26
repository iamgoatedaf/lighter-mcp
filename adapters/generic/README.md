# Lighter MCP — generic MCP client adapter

Any MCP-compatible agent can run `lighter-mcp` over stdio.

## stdio (recommended)

Spawn the server as a subprocess of your agent runtime:

```bash
LIGHTER_MCP_CONFIG=~/.lighter/lighter-mcp/config.toml \
  /path/to/.venv/bin/lighter-mcp stdio
```

The first JSON-RPC request the client sends should be the standard MCP
`initialize`; the server replies with capabilities and the tool catalog
follows from `tools/list`.

## Streamable HTTP

For agents that prefer HTTP transport, install the extras and run a daemon:

```bash
pip install -e /path/to/lighter-mcp[http]
lighter-mcp serve --host 127.0.0.1 --port 8791
```

The MCP endpoint is `http://127.0.0.1:8791/mcp`.

## Tool catalog

Use the `tools/list` MCP method to enumerate; tools are grouped by name
prefix:

- `lighter_market_*`, `lighter_account_*`, `lighter_orders_*` — read-only.
- `lighter_paper_*` — paper trading (mode ≥ `paper`).
- `lighter_live_*` — live writes (mode ≥ `live`).
- `lighter_funds_*` — transfers and withdrawals (mode = `funds`).
- `lighter_safety_status`, `lighter_health`, `lighter_version` — diagnostics.

## Safety contract

Every agent integrating this server must implement the same two-step
confirmation flow described in `adapters/cursor/rules/lighter-safety.mdc` and
`adapters/claude/skill/SKILL.md`.
