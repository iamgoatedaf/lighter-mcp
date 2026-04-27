# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `lighter-mcp init` one-shot installer: clones `lighter-agent-kit`
  (git or HTTPS tarball fallback), writes a default readonly config,
  patches the MCP config of every detected agent (Cursor, Claude Code,
  Claude Desktop, Codex), and copies slash-commands / `lighter-trader`
  sub-agent / post-trade hook scaffolds into each.
- PyPI release: `pip install lighter-mcp` and `pipx install lighter-mcp`
  now work end-to-end. The wheel ships adapter scaffolds and config
  templates as package data so `init` works without the source repo.
- Multi-arch Docker image at `ghcr.io/iamgoatedaf/lighter-mcp` (amd64 +
  arm64), with `lighter-agent-kit` pre-cloned at `/opt/lighter-agent-kit`.
- `release.yml` workflow that builds sdist + wheel, publishes to PyPI
  via Trusted Publishing, pushes the Docker image to GHCR, and drafts a
  GitHub Release on each `vX.Y.Z` tag.
- Homebrew formula skeleton at `packaging/homebrew/lighter-mcp.rb` and
  Smithery manifest at `smithery.yaml` (catalog submissions tracked in
  `ROADMAP.md`).
- 16 unit tests for the `installer` module covering agent detection,
  MCP-JSON patching (including alternate `mcp.servers` shape and
  quarantining invalid input), default-config writing, and the
  git/tarball kit auto-install paths.

### Fixed

- Codex plugin: `plugin.json` references `./.mcp.json`, but no such file
  was ever placed inside `.codex-plugin/`. `install_codex_plugin` now
  generates a `.mcp.json` with the user's actual `lighter-mcp` path and
  config path inside the installed plugin directory.

### Changed

- `install.sh` is now a 30-line shim that delegates to `lighter-mcp init`,
  preserving backwards compatibility for anyone whose docs or muscle
  memory still reaches for `bash install.sh`.

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
