# Lighter MCP — Claude adapter

Two targets — they have **different capabilities**:

| Feature                      | Claude Code | Claude Desktop |
|------------------------------|:-----------:|:--------------:|
| MCP `lighter_*` tools        |     ✅      |       ✅       |
| Slash commands               |     ✅      |       ❌       |
| Sub-agents                   |     ✅      |       ❌       |
| Hooks                        |     ✅      |       ❌       |
| Skill / instructions context |     ✅      |       ✅       |

For Claude Desktop the only artifacts you can install are the MCP server
itself and the `skill/SKILL.md` (delivered via the system prompt). Slash
commands and sub-agents do not exist on that surface.

> **You probably don't need this guide.** `lighter-mcp init` auto-detects
> Claude Code (`~/.claude/`) and Claude Desktop and wires both with one
> command:
>
> ```bash
> lighter-mcp init --agents claude-code,claude-desktop
> ```
>
> Read on only for manual setup or to debug the auto-installer.

## 1. Install the MCP server

Same as for Cursor. See `../cursor/README.md` step 1, or just run the
top-level `install.sh`.

## 2. Register the MCP server

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) — `claude_desktop_config.example.json` is the template. Restart
Claude Desktop; the tools appear under the MCP hammer icon as `lighter_*`.

### Claude Code

```bash
mkdir -p .claude
cp claude_code_config.example.json .claude/mcp.json
claude mcp restart
```

## 3. Skill (both Desktop and Code)

```bash
mkdir -p ~/.claude/skills/lighter
cp adapters/claude/skill/SKILL.md ~/.claude/skills/lighter/
```

This is the agent-facing safety contract. It is the **only** way to
constrain Claude Desktop's behavior — it has no rule/hook system.

## 4. Slash commands (Claude Code only)

```bash
mkdir -p .claude/commands
cp adapters/_shared/commands/*.md .claude/commands/
```

You now have `/lighter-status`, `/lighter-positions`, `/lighter-kill`,
`/lighter-paper`, `/lighter-audit`. They share prompts with the Cursor
versions because the underlying MCP tools are identical.

## 5. Sub-agent `lighter-trader` (Claude Code only)

```bash
mkdir -p .claude/agents
cp adapters/_shared/agents/lighter-trader.md .claude/agents/
```

Invoke it via Claude Code's sub-agent mechanism. It has a narrow tool
budget (only `lighter_*`) and refuses to edit source code.

## 6. After-trade hook (Claude Code only)

```bash
mkdir -p .claude/hooks
cp adapters/_shared/hooks/after-lighter-trade.sh .claude/hooks/post-tool-call.sh
chmod +x .claude/hooks/post-tool-call.sh
```

The hook receives the post-tool-call payload on stdin and appends a
one-line summary to `~/.lighter/lighter-mcp/notifications.log`.

## What's where

```
adapters/claude/
├── README.md                          ← this file
├── claude_desktop_config.example.json
├── claude_code_config.example.json
├── skill/SKILL.md                     ← canonical agent prompt for Claude
├── commands/                          ← symlinks → _shared/commands/
└── agents/                            ← symlinks → _shared/agents/
```
