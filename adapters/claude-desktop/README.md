# Lighter MCP — Claude Desktop notes

Claude Desktop has only **one** integration surface for third-party
servers: the MCP tools list. It does not expose slash commands, sub-agents,
hooks, or rule files. Anything outside of the tool catalog has to be
delivered through the system prompt / SKILL.

## What you can install

| Artifact         | Available in Claude Desktop |
|------------------|:---------------------------:|
| `lighter_*` MCP tools     | ✅ |
| `SKILL.md` (system prompt context) | ✅ (manual paste) |
| Slash commands `/lighter-*` | ❌ — not a Claude Desktop concept |
| Sub-agent `lighter-trader`  | ❌ |
| Post-tool-call hook         | ❌ |

For all the missing UI, use **Claude Code** (`adapters/claude/README.md`)
or **Cursor** (`adapters/cursor/README.md`) instead — they share the same
shared command / agent / hook source.

## Installing the MCP server in Claude Desktop

1. Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
   (macOS) or the equivalent on your platform. Use
   `../claude/claude_desktop_config.example.json` as a starting point and
   replace the placeholder paths with absolute paths to your `lighter-mcp`
   binary and config file.
2. Restart Claude Desktop. The new tools appear under the MCP hammer
   icon as `lighter_*`.

## Installing the SKILL contract

Claude Desktop has no skills folder, so the SKILL contract is delivered
as a **system / project prompt**:

1. Open `../claude/skill/SKILL.md`.
2. Paste it into the project's system prompt or the conversation system
   message.
3. Re-paste it on a fresh chat — there is no auto-attachment.

This is the only way to enforce two-step confirmation behavior on
Claude Desktop. Without it, the agent will still call `lighter_live_*`
tools but may skip the preview step Cursor's `.mdc` rule normally
enforces.

## Recommendation

Use Claude Desktop only for read-only or paper sessions, where the
worst-case is a wrong query. For live trading prefer Cursor or Claude
Code where the safety rule, sub-agent, and hook are enforceable
artifacts.
