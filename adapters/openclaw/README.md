# Lighter MCP — OpenClaw adapter

OpenClaw is an always-on personal-assistant gateway that fans out to channels
like Telegram, WhatsApp, Slack, Discord, and CLI. Because inbound channel
messages are untrusted, this adapter prefers the long-lived HTTP transport
and ships a hardening checklist for Telegram in particular.

## 1. Run the server as a daemon

Install the HTTP extras:

```bash
.venv/bin/pip install -e /path/to/lighter-mcp[http]
```

Run it as a localhost daemon:

```bash
.venv/bin/lighter-mcp serve --host 127.0.0.1 --port 8791
```

For systemd / launchd / pm2 supervision, use the example process spec in
`daemon.example.toml`.

## 2. Point OpenClaw at the daemon

In your OpenClaw configuration, add an MCP server pointing at the local
daemon URL. Use `mcp.example.json` as a template.

## 3. Apply the Telegram safety checklist

Read `telegram-safety.md` end-to-end before exposing this adapter on any
channel. Highlights:

- Allowlist Telegram user ids; reject everyone else.
- Require an explicit pairing handshake before any `lighter_live_*` or
  `lighter_funds_*` tool can fire.
- Keep `mode = "readonly"` or `mode = "paper"` on the gateway by default;
  flip to `"live"` only on a dedicated, authenticated session.
- Never echo `confirmation_id` values into shared channels (groups, supergroups).

## 4. Map slash-style commands

Telegram bots have their own command syntax (`/status`, `/positions`,
`/kill`). Bind those to the **same prompts** Cursor / Claude Code use
under `adapters/_shared/commands/`. Suggested mapping for a Telegram
front-end:

| Telegram command | Source prompt                                  |
|------------------|------------------------------------------------|
| `/status`        | `adapters/_shared/commands/lighter-status.md`  |
| `/positions`     | `adapters/_shared/commands/lighter-positions.md` |
| `/kill`          | `adapters/_shared/commands/lighter-kill.md`    |
| `/paper`         | `adapters/_shared/commands/lighter-paper.md`   |
| `/audit`         | `adapters/_shared/commands/lighter-audit.md`   |

OpenClaw's bot worker should load the markdown body, prepend the user's
message, and feed it to the agent runtime. Sub-agent and hook concepts
do not have direct Telegram analogues; for hooks, post a one-line
summary back to the originating chat after every successful
`lighter_(live|funds)_*` tool call, gated behind the user allowlist.
