# Live PnL watcher + ergonomic trade CLI

A two-pane terminal workflow for paper trading on Lighter:

- **Pane 1 — `watch.sh`**: connects to the Lighter mainnet WebSocket,
  subscribes to order books for every market you currently hold a paper
  position in, and re-renders unrealized PnL on every push (~50–200 ms).
- **Pane 2 — `trade.sh`**: a thin wrapper around the kit's
  `scripts/paper.py` so you can fire `long`, `short`, `status`,
  `positions`, etc. without typing the full path.

The watcher hot-reloads `paper-state.json` on `mtime` change, so any
order placed in pane 2 — or by an MCP-driven agent in another window —
updates the PnL view automatically.

```text
┌─ Pane 1: watch.sh ────────────────────────────────────┐  ┌─ Pane 2: trade.sh ──────────────┐
│ === Lighter Paper PnL — 22:14:03.812 (tick #218) ===  │  │ $ ./trade.sh long SOL 50         │
│   SOL  long   size=    50.0000  entry=$  87.0001      │  │ {"status":"filled", ...}         │
│        mark=$ 87.1934  sp= 1.2bps  uPnL=$    +9.66    │  │ $ ./trade.sh short BTC 0.001     │
│   BTC  long   size=     0.0010  entry=$ 78605.0000    │  │ {"status":"filled", ...}         │
│        mark=$79172.1500  sp= 0.4bps  uPnL=$    +0.57  │  │ $ ./trade.sh status              │
│                                                       │  │ ...                              │
│   Total uPnL:   $+10.23                               │  │                                  │
│   Collateral:   $9,913.34                             │  │                                  │
│   Equity:       $9,923.57                             │  │                                  │
│ Ctrl+C to exit • paper-state auto-reloads on change   │  │                                  │
└───────────────────────────────────────────────────────┘  └──────────────────────────────────┘
```

## Requirements

- A working `lighter-agent-kit` checkout. Easiest:
  ```bash
  pipx install lighter-mcp && lighter-mcp init
  ```
  This clones the kit to `~/.lighter/lighter-agent-kit`, sets up its
  venv (which already includes `lighter-sdk` + `websockets`), and
  writes `kit_path` into `~/.lighter/lighter-mcp/config.toml` so the
  scripts here can find it automatically.
- A paper account. From `~/.lighter/lighter-agent-kit`:
  ```bash
  .venv/bin/python scripts/paper.py init                      # default $10k
  .venv/bin/python scripts/paper.py init --collateral 1000000 \
      --tier premium_7                                         # custom
  ```
  Or via MCP: `lighter_paper_init { collateral: 1000000, tier: "premium_7" }`.
- macOS or Linux.
- A VPN that exits in an allowed jurisdiction. Lighter's `/stream` WS
  endpoint is geo-restricted at the CloudFront edge — from a restricted
  region the handshake returns HTTP 400 with `code: 20558`.

## Quick start (macOS)

```bash
cd examples/live-pnl-watcher
chmod +x watch.sh trade.sh start.sh
./start.sh    # opens two Terminal.app windows
```

That's it. The first window starts `watch.sh`, the second is a prompt
ready for `trade.sh` commands.

## Quick start (any OS, manual)

Open two terminals.

**Window 1** (the watcher):
```bash
cd examples/live-pnl-watcher
./watch.sh
```

**Window 2** (the trade CLI):
```bash
cd examples/live-pnl-watcher
./trade.sh status
./trade.sh long SOL 50
./trade.sh short BTC 0.001
```

## `trade.sh` reference

| Command                                          | What it does |
|--------------------------------------------------|---|
| `./trade.sh long SYMBOL AMOUNT`                  | Market buy. Alias of `buy`. |
| `./trade.sh short SYMBOL AMOUNT`                 | Market sell. Alias of `sell`. |
| `./trade.sh buy SYMBOL AMOUNT`                   | Market buy. |
| `./trade.sh sell SYMBOL AMOUNT`                  | Market sell. |
| `./trade.sh status`                              | Account overview (collateral, equity, fees). |
| `./trade.sh positions`                           | Open positions with entry / mark / PnL. |
| `./trade.sh trades`                              | Trade history. |
| `./trade.sh health`                              | Quick paper-engine sanity check. |
| `./trade.sh raw <paper.py args ...>`             | Pass-through to the kit. Any subcommand works. |

Examples of `raw` pass-through:

```bash
# limit orders (no shortcut wrapper for these yet)
./trade.sh raw order limit SOL --side buy --amount 50 --price 80

# fresh paper account with custom capital + fee tier
./trade.sh raw reset --collateral 1000000 --tier premium_7

# close a single position
./trade.sh raw close SOL
```

## `watch.sh` reference

| Flag             | Default                                            | Notes |
|------------------|----------------------------------------------------|---|
| `--state PATH`   | `~/.lighter/lighter-agent-kit/paper-state.json`    | Override the paper-state file location. |
| `--host HOST`    | `mainnet.zklighter.elliot.ai`                      | WS host without scheme. Use `testnet.zklighter.elliot.ai` for testnet. |
| `--debug`        | off                                                | Print raw WS messages to stdout (chatty). |

`watch.sh` exits with code `0` if there are no open positions and prints
a hint. Open a position in pane 2 and rerun.

## How kit-path resolution works

Both `watch.sh` and `trade.sh` resolve the kit checkout in this order:

1. `$LIGHTER_KIT_PATH` env var (highest priority).
2. `kit_path = "..."` in `~/.lighter/lighter-mcp/config.toml`. This is
   what `lighter-mcp init` writes, so by default no setup is needed.
3. Hard fail with a help message.

Override at runtime:

```bash
LIGHTER_KIT_PATH=/opt/lighter-agent-kit ./watch.sh
```

## Geo-blocking note

Lighter's `/stream` WebSocket lives behind CloudFront with geo-rules.
From a restricted region the connection is refused at the edge with:

```
{"code": 20558, "message": "You are accessing Lighter from a restricted jurisdiction."}
```

Connect via a VPN exiting in an allowed jurisdiction. The watcher pins
the SDK's User-Agent (`OpenAPI-Generator/1.0.0/python`) on the WS
handshake just in case a future edge rule starts gating WebSockets by
UA the way the REST allowlist does today.

## Why these scripts and not just MCP tools?

- **MCP tools** (`lighter_paper_market_order`, `lighter_account_get_positions`,
  …) are designed for an agent to call. They return JSON, validate
  inputs, audit every call, and gate live writes behind two-step
  confirmation. That's the right surface for an LLM.
- **These scripts** are designed for a human at a keyboard who wants
  sub-second visual feedback while testing strategies. They share the
  same paper-state file as the MCP, so you can interleave: open a
  position in pane 2, watch the agent reason about it in your IDE, see
  the PnL move in pane 1, all on the same simulated book.

## Architecture

```text
                 ┌──────────────────────────────────────┐
                 │  Lighter mainnet (CloudFront → WS)   │
                 └──────────────────┬───────────────────┘
                                    │ wss://.../stream
                                    │ (order book deltas)
                                    ▼
              ┌────────────────────────────────────────┐
              │  watch.py  (uses kit's venv via .sh)   │
              │  - subscribes to held markets only     │
              │  - mid = (best_bid + best_ask) / 2     │
              │  - reloads paper-state.json on mtime   │
              └─────────────────────┬──────────────────┘
                                    │ reads
                                    ▼
              ┌────────────────────────────────────────┐
              │  ~/.lighter/lighter-agent-kit/         │
              │     paper-state.json                   │
              │  ▲                                     │
              │  │ writes                              │
              └──┼─────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
  ┌───────────┐    ┌───────────────────┐
  │ trade.sh  │    │  Lighter MCP      │
  │ (you)     │    │  (your AI agent)  │
  └───────────┘    └───────────────────┘
```

## Troubleshooting

| Symptom                                               | Cause / fix |
|-------------------------------------------------------|---|
| `Could not locate a lighter-agent-kit checkout`       | Set `$LIGHTER_KIT_PATH` or run `lighter-mcp init`. |
| `kit python not found at ...`                         | Run the kit's `install.sh` to create its venv. |
| `paper-state not found at ...`                        | Run `./trade.sh raw init` (or `paper.py init`). |
| WS hangs at `Connecting to wss://...`                 | Geo-block. Switch on your VPN. |
| `HTTP 400` / `code: 20558` on connect                 | Same — geo-block. |
| Watcher shows `mark = —` for several seconds after start | Normal — wait for the first book snapshot to arrive on each subscribed market. |
| PnL doesn't update after I placed an order            | Confirm the order actually filled (`./trade.sh positions`). The watcher only reloads when `paper-state.json` changes mtime. |

## License

Same as the parent repo (MIT). See [LICENSE](../../LICENSE).
