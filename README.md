# Lighter MCP Toolkit

[![CI](https://github.com/iamgoatedaf/lighter-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/iamgoatedaf/lighter-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/lighter-mcp.svg)](https://pypi.org/project/lighter-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/lighter-mcp.svg)](https://pypi.org/project/lighter-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-1.2%2B-purple.svg)](https://modelcontextprotocol.io)

> **Read this first:** live orders and withdrawals on Lighter are
> irreversible. Read [DISCLAIMER.md](DISCLAIMER.md) before flipping
> `mode = "live"` or `mode = "funds"`.

A portable Model Context Protocol server that exposes Lighter trading to
any MCP-capable agent — Cursor, Claude Code, Claude Desktop, Codex,
OpenClaw, and generic MCP clients — with **safety as a first-class
concern**, not an afterthought.

The server wraps the official
[`lighter-agent-kit`](https://github.com/elliottech/lighter-agent-kit)
Python scripts via subprocess and adds:

- **Typed Pydantic input schemas** with regex-validated symbols and
  asset codes (no command-line argument injection).
- **Mode-based safety gates** (`readonly` → `paper` → `live` → `funds`):
  the tool catalog grows monotonically; live and funds tools physically
  do not exist in the catalog until you opt in.
- **Two-step confirmations** for every fund-loss path: first call returns
  a preview + single-use token, second call with the token executes.
  Tokens are bound to tool name + argument digest and TTL-limited.
- **Atomic, UTC-keyed daily-notional ledger** that fail-safes to
  `cap exhausted` if its file is corrupt — never silently resets to 0.
- **Append-only audit log** with sanitized argv/result, intra-process
  lock + POSIX `flock`, and soft-fail on disk errors.
- **Streamable-HTTP transport** that refuses to bind non-loopback hosts
  unless `--allow-remote` is passed (the server has no built-in auth).

## Why not just use the kit directly?

The kit is a CLI for a human. This server is the safety harness for a
**non-human caller**. Every call is schema-validated, gate-checked,
audited, and (for write paths) preview-confirmed before any subprocess
runs against the exchange. The agent literally cannot reach the kit
without going through these layers.

## Quick start

One command, end to end:

```bash
pipx install lighter-mcp && lighter-mcp init
```

`lighter-mcp init` clones the upstream `lighter-agent-kit` into
`~/.lighter/lighter-agent-kit`, writes a default **readonly** config to
`~/.lighter/lighter-mcp/config.toml`, and auto-wires every MCP-capable
agent it finds locally — Cursor, Claude Code, Claude Desktop, Codex —
including slash-commands, the `lighter-trader` sub-agent, and the
post-trade hook. Restart your agent and try:

> /lighter-status

That's it. Live trading stays OFF until you flip it on in the config and
re-run `lighter-mcp doctor`.

### Other ways to install

<details>
<summary><b>uvx (zero install, ephemeral)</b></summary>

```bash
uvx lighter-mcp init
```

`uvx` runs the published wheel from a cached venv. Good for one-off
exploration; for steady-state use prefer `pipx install` so the agent
config can point at a stable executable path.

</details>

<details>
<summary><b>Docker (GHCR)</b></summary>

```bash
docker pull ghcr.io/iamgoatedaf/lighter-mcp:0.1.0
docker run --rm -it -v ~/.lighter:/data \
    ghcr.io/iamgoatedaf/lighter-mcp:0.1.0 \
    lighter-mcp init --no-scaffolds
```

The image ships with the kit pre-cloned at `/opt/lighter-agent-kit` and
runs `lighter-mcp serve` on `:8791` by default.

</details>

<details>
<summary><b>From source (development)</b></summary>

```bash
git clone https://github.com/iamgoatedaf/lighter-mcp
cd lighter-mcp
python3 -m venv .venv && .venv/bin/pip install -e ".[dev,http]"
.venv/bin/lighter-mcp init
```

</details>

After any path above, `lighter-mcp doctor` should print a green health envelope.

## Modes and tools

| Mode      | Reads | Paper trading | Live trading | Transfers / Withdrawals | Tools |
|-----------|:-----:|:-------------:|:------------:|:-----------------------:|:-----:|
| readonly  | ✅    | —             | —            | —                       | 18    |
| paper     | ✅    | ✅            | —            | —                       | 29    |
| live      | ✅    | ✅            | gated        | —                       | 37    |
| funds     | ✅    | ✅            | gated        | gated                   | 39    |

`live` and `funds` additionally require explicit `[live]` / `[funds]`
config blocks with allowlists, notional caps, leverage caps, and
confirmation flags. See [`docs/configuration.md`](docs/configuration.md).

## Slash commands and sub-agent (Cursor / Claude Code / Codex)

The adapters ship a pre-built UI layer driven by the same MCP tools:

| Command              | What it does |
|----------------------|--------------|
| `/lighter-status`    | Active mode, daily-notional remaining, equity, open orders. |
| `/lighter-positions` | Positions with entry / mark / PnL / liq distance. |
| `/lighter-kill`      | Panic close: `cancel_all` + `close_all`, two-step confirm with the literal word `confirm`. |
| `/lighter-paper`     | Switch active mode to paper. Prompts before editing config. |
| `/lighter-audit`     | Tail the audit log with filters (last N hours, only failures, by tool). |

Plus a dedicated **`lighter-trader` sub-agent** with a narrow
`lighter_*`-only tool budget that cannot edit source files and refuses to
chain a kill without an explicit confirmation word.

The single source of truth for these prompts lives in
[`adapters/_shared/`](adapters/_shared/). Per-platform folders are
symlinks back into it.

## Agent adapters

| Platform        | MCP tools | SKILL / system prompt | Slash commands | Sub-agent | Hook | Auto-install |
|-----------------|:--:|:--:|:--:|:--:|:--:|---|
| Cursor          | ✅ | rule (`.mdc`) | ✅ | ✅ | ✅ | `lighter-mcp init --agents cursor` |
| Claude Code     | ✅ | SKILL.md | ✅ | ✅ | ✅ | `lighter-mcp init --agents claude-code` |
| Claude Desktop  | ✅ | SKILL paste | ❌ | ❌ | ❌ | `lighter-mcp init --agents claude-desktop` |
| Codex           | ✅ | SKILL.md | ✅ | ✅ | ✅ | `lighter-mcp init --agents codex` |
| OpenClaw / Telegram | ✅ | mapping doc | bot-side | ❌ | bot-side | manual — see [`adapters/openclaw/`](adapters/openclaw/) |
| Generic MCP     | ✅ | by hand | — | — | — | see [`adapters/generic/`](adapters/generic/) |

`lighter-mcp init` (no `--agents`) detects all installed agents at once.
Per-platform READMEs explain exactly which UI surfaces exist for that
agent and which require workarounds.

## Examples

End-to-end walkthroughs in [`examples/`](examples/):

- [`paper-demo.md`](examples/paper-demo.md) — first paper trade,
  step-by-step.
- [`guarded-live-order.md`](examples/guarded-live-order.md) — full
  two-step confirm flow on `lighter_live_market_order`.
- [`funding-scan.md`](examples/funding-scan.md) — read-only scan of
  funding rates across symbols.
- [`live-pnl-watcher/`](examples/live-pnl-watcher/) — two-pane
  terminal workflow: a WebSocket-driven PnL view that hot-reloads on
  `paper-state.json` changes, plus a `trade.sh` CLI wrapper for
  long/short/status while the watcher is running.

**Hosted documentation site** — [`website/`](website/) is a Mintlify
project. Push to GitHub and Mintlify auto-deploys the site at
`https://lighter-mcp.mintlify.app` (or your custom domain). Local
preview: `cd website && npm run dev`.

Markdown deep-dives in [`docs/`](docs/) (legacy / source material for
the site):

- [`getting-started.md`](docs/getting-started.md)
- [`configuration.md`](docs/configuration.md) — every key in the TOML.
- [`audit-log.md`](docs/audit-log.md) — record format, redaction rules,
  retention strategy.
- [`security.md`](docs/security.md) — companion to top-level
  [`SECURITY.md`](SECURITY.md).

## Development

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev,http]"
.venv/bin/ruff check .
.venv/bin/pytest -q   # 53 tests, fully hermetic by default
```

Tests that need a real `lighter-agent-kit` checkout are auto-skipped
unless `LIGHTER_KIT_PATH` is set. See [`CONTRIBUTING.md`](CONTRIBUTING.md)
for the contribution workflow and the bar for changes that touch
`safety.py`, `confirmations.py`, or any `lighter_live_*` /
`lighter_funds_*` tool.

## Compatibility notes

- Tested against `lighter-agent-kit` as of April 2026. The wrapper relies
  on the kit's `query.py` / `trade.py` / `paper.py` script entry points
  and their JSON stdout contracts — pin to a known-good kit commit if
  you fork.
- Python ≥ 3.10. Built and tested on macOS and Ubuntu; Windows works for
  the server itself, but the per-platform adapters use symlinks — run
  [`adapters/_shared/sync.sh`](adapters/_shared/sync.sh) to materialize
  them as real files.

## Project status

**Alpha (`0.1.0`).** Tool surface is stable enough to use, but expect
schema-level breaking changes between minor versions until `1.0`. See
[`CHANGELOG.md`](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
