# OpenClaw integration

See [`adapters/openclaw/README.md`](../../adapters/openclaw/README.md) for
install and [`adapters/openclaw/telegram-safety.md`](../../adapters/openclaw/telegram-safety.md)
for the channel-side hardening checklist.

## Architecture

```
[ Telegram ] --→ [ OpenClaw gateway ] --MCP/HTTP--→ [ lighter-mcp serve ] --subprocess--→ [ kit ] --→ [ Lighter ]
```

The MCP daemon binds to `127.0.0.1` only. Inbound chat messages are
allowlisted and paired by OpenClaw before they reach the agent. The agent
calls `lighter_*` tools the same way it would from any other transport.

## Recommended deployment

- One daemon per principal. Don't reuse a single `lighter-mcp` daemon for
  multiple users.
- Run the daemon on the same host as OpenClaw, never across an open network.
- Keep the daemon's `mode` at the lowest level needed for your channel.
