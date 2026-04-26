# Getting started

This guide walks through a fresh install on macOS / Linux. Total time: ~5 minutes.

## Prerequisites

- Python 3.10+ on PATH (`python3.11` recommended).
- A working
  [`lighter-agent-kit`](https://github.com/elliottech/lighter-agent-kit)
  checkout with its venv built. Install it first if you haven't:

  ```bash
  curl -fsSL https://github.com/elliottech/lighter-agent-kit/releases/latest/download/install.sh | bash
  ```

## 1. Install lighter-mcp

```bash
git clone https://github.com/<org>/lighter-mcp /path/to/lighter-mcp
cd /path/to/lighter-mcp
bash install.sh --kit-path /path/to/lighter-agent-kit
```

The installer:

1. Locates Python 3.10+ on your system.
2. Creates a venv at `~/.lighter/lighter-mcp/venv/`.
3. Installs `lighter-mcp` editable.
4. Writes `~/.lighter/lighter-mcp/config.toml` in `readonly` mode.
5. Runs `lighter-mcp doctor` to confirm reachability of Lighter.

## 2. Connect your agent

Pick the adapter that matches your runtime:

- Cursor: `adapters/cursor/README.md`
- Claude Desktop / Code: `adapters/claude/README.md`
- Codex: `adapters/codex/README.md`
- OpenClaw / Telegram: `adapters/openclaw/README.md`
- Anything else with MCP support: `adapters/generic/README.md`

## 3. Try a read

In your agent, ask:

> What's the current funding rate for BTC on Lighter?

The agent should call `lighter_market_funding` with `symbol = "BTC"` and
return the answer.

## 4. Try paper trading

Edit `~/.lighter/lighter-mcp/config.toml` to `mode = "paper"`, restart the
MCP server, then ask:

> Open a paper account, then go long 0.01 BTC at market.

The agent should call `lighter_paper_init` followed by
`lighter_paper_market_order`.

## 5. Going live

Read [`DISCLAIMER.md`](../DISCLAIMER.md) and [`SECURITY.md`](../SECURITY.md).
Then promote your config to `mode = "live"`, fill in the `[live]` block with
narrow caps, and restart the server. Every live tool will go through a
preview/confirm cycle; never approve one without reading the plan back to
the user.
