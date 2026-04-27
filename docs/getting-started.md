# Getting started

This guide walks through a fresh install on macOS / Linux. Total time: ~2 minutes.

## Prerequisites

- Python 3.10+ on PATH (`python3.11` recommended).
- `pipx` (`brew install pipx` / `python3 -m pip install --user pipx`).
- `git` is recommended (used to clone the upstream
  [`lighter-agent-kit`](https://github.com/elliottech/lighter-agent-kit)).
  If `git` is missing, `lighter-mcp init` falls back to a tarball download
  over HTTPS — no extra binaries required.

## 1. Install lighter-mcp

```bash
pipx install lighter-mcp && lighter-mcp init
```

`lighter-mcp init` performs end-to-end first-time setup:

1. Clones `lighter-agent-kit` into `~/.lighter/lighter-agent-kit`
   (or downloads a tarball if `git` isn't available).
2. Writes `~/.lighter/lighter-mcp/config.toml` in `readonly` mode.
3. Detects locally installed agents (Cursor, Claude Code, Claude Desktop,
   Codex) and patches each one's MCP config to launch `lighter-mcp stdio`.
4. Drops in slash-commands, the `lighter-trader` sub-agent, and the
   post-trade hook for agents that support those surfaces.
5. Runs `lighter-mcp doctor` as a smoke check.

## 2. Try a read

Restart your agent (Cursor / Claude / Codex) so it picks up the new MCP
server, then ask:

> What's the current funding rate for BTC on Lighter?

The agent should call `lighter_market_funding` with `symbol = "BTC"` and
return the answer. Or run the slash command:

> /lighter-status

## 3. Try paper trading

Edit `~/.lighter/lighter-mcp/config.toml` to `mode = "paper"`, restart the
MCP server, then ask:

> Open a paper account, then go long 0.01 BTC at market.

The agent should call `lighter_paper_init` followed by
`lighter_paper_market_order`.

## 4. Going live

Read [`DISCLAIMER.md`](../DISCLAIMER.md) and [`SECURITY.md`](../SECURITY.md).
Then promote your config to `mode = "live"`, fill in the `[live]` block with
narrow caps, and restart the server. Every live tool will go through a
preview/confirm cycle; never approve one without reading the plan back to
the user.

## Manual install (advanced)

If you cannot use `pipx`, want a development checkout, or are wiring an
agent the auto-detector doesn't recognise yet, see the per-platform
adapter README:

- Cursor: [`adapters/cursor/README.md`](../adapters/cursor/README.md)
- Claude Code / Desktop: [`adapters/claude/README.md`](../adapters/claude/README.md)
- Codex: [`adapters/codex/README.md`](../adapters/codex/README.md)
- OpenClaw / Telegram: [`adapters/openclaw/README.md`](../adapters/openclaw/README.md)
- Anything else with MCP support: [`adapters/generic/README.md`](../adapters/generic/README.md)
