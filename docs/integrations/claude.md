# Claude integration (Desktop / Code)

See [`adapters/claude/README.md`](../../adapters/claude/README.md) for
install. The `claude_desktop_config.example.json` and
`claude_code_config.example.json` files are drop-in templates.

## Skill discovery

Claude products honor the agentskills.io spec via `~/.claude/skills/`. Drop
the bundled `skill/SKILL.md` there to teach Claude when to call the tools
versus the kit's CLI directly. The skill's frontmatter `description` is what
Claude uses to decide whether to load it for a given conversation.

## When to prefer CLI over MCP

The MCP server is faster (one persistent process versus subprocess-per-call
when invoking the kit by hand) and gives you the safety + audit layers. Use
the kit's CLI directly only for ad-hoc terminal usage outside an agent
session.
