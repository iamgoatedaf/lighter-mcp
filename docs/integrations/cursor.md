# Cursor integration

See [`adapters/cursor/README.md`](../../adapters/cursor/README.md) for the
mechanical install and the optional safety rule.

## How agents discover the tools

After registering the server in `.cursor/mcp.json`, Cursor's agent sees the
MCP tool catalog at the start of each conversation. Tool names are
`lighter_*`; the inline description encodes the safety contract.

## Recommended workflow

- Always keep the safety rule installed so two-step confirmations are
  enforced by the rule layer, not just by your prompts.
- Switch modes by editing `~/.lighter/lighter-mcp/config.toml` and reloading
  the MCP server (Command Palette → *Reload MCP servers*).
- For trading sessions where you need the agent to be silent on read-only
  data, point it at a separate config with `mode = "readonly"`.
