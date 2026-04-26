# Configuration reference

`lighter-mcp` reads a single TOML file. Resolution order:

1. `--config <path>` flag.
2. `$LIGHTER_MCP_CONFIG` env var.
3. `~/.lighter/lighter-mcp/config.toml`.
4. Built-in defaults — used only when none of the above exist *and*
   `$LIGHTER_KIT_PATH` is set.

## Top-level keys

| Key                   | Type   | Default                                | Notes                                                                |
| --------------------- | ------ | -------------------------------------- | -------------------------------------------------------------------- |
| `mode`                | string | `readonly`                             | One of `readonly`, `paper`, `live`, `funds`.                         |
| `kit_path`            | path   | required                               | Absolute path to a working `lighter-agent-kit` checkout.             |
| `python_executable`   | path   | `<kit_path>/.venv/bin/python`          | Override only if the kit's venv lives elsewhere.                     |
| `audit_log`           | path   | `~/.lighter/lighter-mcp/audit.jsonl`   | Append-only JSONL.                                                   |
| `confirmation_ttl_s`  | int    | `120`                                  | Confirmation-token lifetime in seconds.                              |
| `host`                | string | `https://mainnet.zklighter.elliot.ai`  | Lighter API host. Use the testnet host while developing strategies. |

## `[live]`

Required when `mode` is `live` or `funds`. The MCP server refuses to register
write tools unless `enabled = true`.

| Key                       | Type        | Default | Effect                                                                                                  |
| ------------------------- | ----------- | ------- | ------------------------------------------------------------------------------------------------------- |
| `enabled`                 | bool        | `false` | Master switch for live writes.                                                                          |
| `allowed_symbols`         | list[str]   | `[]`    | If non-empty, only listed bases (e.g. `["BTC"]`) may be traded. Empty list = no allowlist (not advised). |
| `max_order_notional_usd`  | float       | `0`     | `0` disables the per-order cap.                                                                         |
| `max_daily_notional_usd`  | float       | `0`     | `0` disables the rolling cap. Counter resets at UTC midnight.                                           |
| `max_leverage`            | int         | `0`     | `0` disables the leverage cap.                                                                          |
| `require_confirmation`    | bool        | `true`  | Disable only if the upstream agent already enforces a preview/approve UX.                              |

## `[funds]`

Required when `mode = "funds"`.

| Key                    | Type  | Default | Effect                                          |
| ---------------------- | ----- | ------- | ----------------------------------------------- |
| `transfers_enabled`    | bool  | `false` | Allow `lighter_funds_transfer`.                 |
| `withdrawals_enabled`  | bool  | `false` | Allow `lighter_funds_withdraw`.                 |
| `max_withdrawal_usd`   | float | `0`     | `0` disables the per-withdrawal cap.            |
| `require_confirmation` | bool  | `true`  | Funds tools always confirm regardless of value. |

## Environment overrides

| Env                    | Effect                                            |
| ---------------------- | ------------------------------------------------- |
| `LIGHTER_MCP_CONFIG`   | Path to the config file.                          |
| `LIGHTER_KIT_PATH`     | Override `kit_path` (mostly for CI / containers). |
| `LIGHTER_HOST`         | Override `host`.                                  |

## Reloading

The server reads the config once at startup. After editing, restart your
agent's MCP connection (Cursor: *Reload MCP servers*; Claude: restart;
Codex: `codex mcp restart`).
