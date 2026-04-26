# Audit log format

Each tool invocation appends one JSON object per line to
`~/.lighter/lighter-mcp/audit.jsonl`.

## Fields

| Field             | Type    | Notes                                                                           |
| ----------------- | ------- | ------------------------------------------------------------------------------- |
| `ts`              | float   | Unix epoch seconds when the call started.                                       |
| `tool`            | string  | The MCP tool name, e.g. `lighter_live_market_order`.                            |
| `mode`            | string  | Active server mode at call time.                                                |
| `ok`              | bool    | Whether the kit subprocess returned without surfacing an error envelope.        |
| `args`            | object  | Sanitized tool arguments. Credential-like keys are replaced with `[REDACTED]`. |
| `result`          | any     | Sanitized parsed JSON from the kit. Two levels of nested objects max.           |
| `confirmation_id` | string  | Preview token consumed (if any). Omitted when not applicable.                   |
| `error`           | string  | Error message when `ok = false`. Omitted otherwise.                             |

## Sanitization

Substrings that trigger redaction (case-insensitive) on `args` and `result`
keys: `private_key`, `secret`, `api_key`, `token`, `signature`, `tx_info`,
`credential`, `passphrase`, `password`, `auth`, `sig`.

String values are truncated to 4 KiB with a `…[truncated]` suffix.

## Operational notes

- The file is append-only. Rotate it externally (e.g., `logrotate`) if it
  grows beyond your retention budget.
- The server keeps no in-memory copy beyond the most recent call; restarting
  does not lose history.
- `daily-notional.json` lives next to the audit file and is overwritten at
  every executed live order. Do not delete it while the server is running
  unless you intend to reset the daily counter.
