# Security model

`lighter-mcp` is designed to run **locally** alongside the agent runtime on
the same trust boundary as your shell. It does not implement transport-level
authentication on its own and assumes the MCP transport (stdio or localhost
HTTP) is itself trusted.

## Threat model

| Threat                                          | Mitigation                                                                                              |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Agent prompt-injection drives a live trade      | Two-step confirmation, mode gating, allowlist, daily-notional cap, audit log                            |
| Agent exfiltrates credentials                   | Server never reads `LIGHTER_API_PRIVATE_KEY` itself; only the kit subprocess does. Args/results sanitized in the audit log |
| Multi-tenant agent shares the daemon            | One config file = one trust domain. Run separate daemons / configs per principal                       |
| Telegram/Slack channel sends a malicious prompt | OpenClaw-side allowlist + pairing handshake; see `adapters/openclaw/telegram-safety.md`                |
| Confirmation token replay                       | Tokens are single-use, scoped by tool name + args digest, and TTL-limited                              |
| Audit log tampering                             | Out-of-scope here. Use OS-level append-only mounts or off-host log forwarding if you need integrity    |

## Trust boundary

```
[ user ] -- prompt --> [ agent ] -- MCP --> [ lighter-mcp ] -- subprocess --> [ kit ] -- HTTPS --> [ Lighter ]
```

The MCP server lives on the user's machine. It does not expose a network
listener by default. The optional Streamable HTTP transport binds to
`127.0.0.1` only and should not be exposed to remote networks. Use SSH port
forwarding if you need remote access.

## Secrets handling

- `lighter-mcp` does **not** read API keys. It always shells into the kit's
  pinned virtualenv, which reads credentials from
  `~/.lighter/lighter-agent-kit/credentials` or env vars per the kit's
  contract.
- The audit log redacts any key whose name matches credential-like
  substrings, plus `tx_info` blobs from signed transaction payloads.
- The audit log truncates oversized strings to 4 KiB.

## Reporting

Found something? Open an issue on the repo with a brief description; if it's
a real vulnerability, mark it private and email the maintainer listed in
`README.md` instead of disclosing publicly.
