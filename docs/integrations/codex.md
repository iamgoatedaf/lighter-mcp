# Codex integration

See [`adapters/codex/README.md`](../../adapters/codex/README.md) for install.

The Codex adapter ships:

- `.mcp.json` — MCP server registration.
- `.codex-plugin/plugin.json` — plugin manifest for ecosystems that index
  Codex plugins.
- `skills/lighter/SKILL.md` — agentskills.io spec (matches the Claude skill).
- `hooks/` — placeholder for Codex pre/post hooks (none ship by default).

## Hook ideas

- `pre-call` for `lighter_live_*`: auto-invoke `lighter_safety_status` and
  print the result to the user before the agent sees the response.
- `post-call` for `lighter_funds_withdraw`: append a row to a separate
  spreadsheet for compliance tracking.

These are illustrative; we don't ship them out of the box because hook
shapes vary across Codex versions.
