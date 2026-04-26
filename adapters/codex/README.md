# Lighter MCP — Codex adapter

Codex consumes MCP servers and the codex-plugin format. The plugin
manifest in `.codex-plugin/plugin.json` already wires up the MCP server,
the SKILL, slash commands, the `lighter-trader` sub-agent, and the
after-trade hook.

## 1. Register the MCP server

Codex Desktop reads `~/.codex/config.toml`. Add a `[mcp_servers.lighter]`
table. Codex CLI / per-project use can copy `.mcp.json` next to the
project root:

```bash
cp adapters/codex/.mcp.json ./.mcp.json
```

Replace `command` and `LIGHTER_MCP_CONFIG` with your real paths.

## 2. Install the plugin

The plugin folder bundles everything Codex needs:

```bash
mkdir -p ~/.codex/plugins
cp -R adapters/codex/.codex-plugin ~/.codex/plugins/lighter
```

This drops in:

- `mcp` → `./.mcp.json` (server config)
- `skills` → `./skills/lighter/SKILL.md`
- `commands` → 5 slash commands (symlinks to `_shared/commands/`)
- `agents` → `lighter-trader` sub-agent (symlink)
- `hooks.postToolCall` → `./hooks/after-lighter-trade.sh`, fires on every
  `lighter_(live|funds)_*` tool call

Restart Codex (or run `codex plugins reload`).

## 3. (Standalone) install just the SKILL

If you do not want the full plugin and only want the agent-facing safety
contract:

```bash
mkdir -p ~/.codex/skills/lighter
cp adapters/codex/skills/lighter/SKILL.md ~/.codex/skills/lighter/
```

## What ships

```
adapters/codex/
├── README.md
├── .mcp.json                            ← server config
├── skills/lighter/SKILL.md              ← agent contract
└── .codex-plugin/
    ├── plugin.json                      ← manifest tying it all together
    ├── commands/                        ← symlinks → _shared/commands/
    ├── agents/                          ← symlinks → _shared/agents/
    └── hooks/after-lighter-trade.sh     ← symlink → _shared/hooks/
```

The shared markdown/scripts under `adapters/_shared/` are the source of
truth — the Codex adapter just provides the manifest stitching.
