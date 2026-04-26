# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-04-26

Initial public release.

### Added

- FastMCP server (`lighter-mcp` console script) wrapping the
  `lighter-agent-kit` Python scripts via subprocess.
- Four-mode safety model: `readonly` / `paper` / `live` / `funds`. Tool
  catalog grows monotonically with mode (18 → 29 → 37 → 39 tools).
- Read tools (`lighter_market_*`, `lighter_account_*`, `lighter_orders_*`,
  `lighter_portfolio_performance`, etc.).
- Paper-trading tools (`lighter_paper_*`).
- Live-trading tools (`lighter_live_*`) gated by:
    - mode + per-symbol allowlist + per-leverage cap;
    - per-order notional cap;
    - daily-notional ledger persisted atomically (UTC-keyed);
    - mandatory two-step confirmation with single-use, args-bound tokens.
- Funds tools (`lighter_funds_withdraw`, `lighter_funds_transfer`) behind
  an additional opt-in.
- Append-only sanitized audit log at `~/.lighter/lighter-mcp/audit.jsonl`,
  with intra-process lock + POSIX `flock` and a soft-fail on write
  errors.
- Streamable-HTTP transport with refusal to bind non-loopback hosts
  unless `--allow-remote` is passed explicitly.
- Doctor smoke check (`lighter-mcp doctor`).
- Adapters for **Cursor**, **Claude Code**, **Claude Desktop**,
  **Codex**, **OpenClaw**, and a generic MCP target.
- Single source of truth for slash-commands, sub-agent, and post-trade
  hook under `adapters/_shared/`.
- Five slash-commands: `/lighter-status`, `/lighter-positions`,
  `/lighter-kill`, `/lighter-paper`, `/lighter-audit`.
- Specialized `lighter-trader` sub-agent with a narrow tool budget.
- After-trade hook posting to a local notifications log + macOS
  Notification Center.
- 53 tests, including regression coverage for an external security audit.
