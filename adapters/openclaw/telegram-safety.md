# Telegram safety checklist for OpenClaw + lighter-mcp

Telegram (and other chat channels) are untrusted input. Treat any inbound
message as if it could be from someone trying to drain the account.

## 1. Authenticate by user id

Pin a Telegram user id allowlist on the OpenClaw side. Reject every other
user *before* the message is forwarded to the agent. Group chats and
supergroups must be excluded from any channel that has live or funds tools
enabled.

## 2. Pair before privileged use

Before the gateway accepts a `lighter_live_*` or `lighter_funds_*` call from
a channel, require a one-time pairing handshake initiated from a trusted
device (e.g., the workstation where `~/.lighter/lighter-mcp/config.toml`
lives). The handshake establishes a session token tied to the chat id.

## 3. Default mode is `readonly`

The default `lighter-mcp` config used by the daemon should have
`mode = "readonly"` or `mode = "paper"`. To take live actions, the user
flips the mode locally on their workstation, then explicitly informs the
gateway. Never let inbound chat messages mutate the config.

## 4. Confirmation hygiene

The two-step confirmation flow already protects against accidental writes,
but tokens must never be echoed into a shared chat. Treat
`confirmation_id` as sensitive: include it only in direct messages to the
authenticated user, never in groups, channels, or message previews.

## 5. Audit log

Each gateway call still goes through the central audit log
(`~/.lighter/lighter-mcp/audit.jsonl`). Periodically review for unexpected
sources or oversize writes.

## 6. Rate limit and notional cap

Layer additional rate limits and a per-channel notional cap on the OpenClaw
side. The lighter-mcp daily cap is per-process; if you run a single daemon
shared between multiple chat channels, channel-side caps prevent any one
chat from monopolizing it.
