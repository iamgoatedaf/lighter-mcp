# Lighter MCP — Cursor adapter

Wires `lighter-mcp` into Cursor as an MCP server, plus the Cursor-native
artifacts that turn the plugin from "just an MCP" into a first-class
trading workflow:

- 5 slash commands (`/lighter-status`, `/lighter-positions`, `/lighter-kill`,
  `/lighter-paper`, `/lighter-audit`).
- A specialized sub-agent **`lighter-trader`** with a narrow tool budget and
  a strict safety contract.
- An after-tool-call hook that records every live/funds write to a local
  notifications log and pings macOS Notification Center.
- The `.mdc` rule that teaches Cursor's main agent the two-step
  confirmation flow.

## 1. Install the MCP server

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e /path/to/lighter-mcp
mkdir -p ~/.lighter/lighter-mcp
cp /path/to/lighter-mcp/configs/lighter-mcp.readonly.toml \
   ~/.lighter/lighter-mcp/config.toml
.venv/bin/lighter-mcp doctor
```

## 2. Register the MCP server

```bash
mkdir -p .cursor
cp adapters/cursor/mcp.example.json .cursor/mcp.json
```

Restart Cursor or run *Reload MCP servers*. The server appears as
**lighter** with all `lighter_*` tools.

## 3. Install the safety rule

```bash
mkdir -p .cursor/rules
cp adapters/cursor/rules/lighter-safety.mdc .cursor/rules/
```

## 4. Install slash commands

The shared command prompts live under `adapters/_shared/commands/`. Copy
them into the Cursor commands folder:

```bash
mkdir -p .cursor/commands
cp adapters/_shared/commands/*.md .cursor/commands/
```

After reloading Cursor, you have:

- `/lighter-status` — mode, daily-notional budget, equity, open orders.
- `/lighter-positions` — positions with entry, mark, PnL, liq distance.
- `/lighter-kill` — panic button: cancel all + close all (two-step confirm).
- `/lighter-paper` — flip the active mode to `paper` (reload required).
- `/lighter-audit` — last N hours of audit-log records with filters.

## 5. Install the `lighter-trader` sub-agent

```bash
mkdir -p .cursor/agents
cp adapters/_shared/agents/lighter-trader.md .cursor/agents/
```

Invoke it from Cursor as a sub-agent (`@lighter-trader …`) when you want a
narrow, code-free trading session. It cannot edit source files and will
always preview live writes before executing.

## 6. Install the after-trade hook

```bash
mkdir -p .cursor
cp adapters/cursor/hooks.json .cursor/hooks.json
```

The hook fires on every `lighter_(live|funds)_*` tool call and:

- Appends a one-line summary to `~/.lighter/lighter-mcp/notifications.log`.
- On macOS, posts a desktop notification via `osascript`.

It never re-calls the MCP server (avoids audit recursion).

## 7. Switching modes

Edit `~/.lighter/lighter-mcp/config.toml`:

- `mode = "readonly"` — public + authenticated reads only.
- `mode = "paper"` — adds paper trading.
- `mode = "live"` — enables live writes; configure the `[live]` block.
- `mode = "funds"` — also enables transfers/withdrawals.

After editing, reload MCP servers (or run `/lighter-paper` for the paper
flip).

## What's where

```
adapters/cursor/
├── README.md                ← this file
├── mcp.example.json         ← .cursor/mcp.json template
├── hooks.json               ← .cursor/hooks.json template
├── rules/lighter-safety.mdc ← copies into .cursor/rules/
├── commands/                ← symlinks into adapters/_shared/commands/
└── agents/                  ← symlinks into adapters/_shared/agents/
```

The shared markdown files are the source of truth; per-platform folders
hold symlinks so a fix in `_shared/` propagates everywhere.
