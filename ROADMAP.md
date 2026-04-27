# Roadmap

This file is the public backlog for everything beyond the work that landed in
`v0.1.0`. It is opinionated about ordering: items are grouped by **what they
unblock**, not by what's easiest to build. The single guiding question is:

> *Does this make a non-human caller safer or make first-time onboarding
> faster?*

Anything that does neither lives in [Out of scope](#out-of-scope) at the
bottom.

## v0.2 — distribution everywhere (in flight)

The work to take the project from "fast in source" to "fast in any of the
five places people install MCP servers". Most of this is already on `main`;
ticking off the remaining items closes out the milestone.

- [x] `lighter-mcp init` subcommand: kit auto-clone, default config,
      multi-agent detection and config patching, slash-command scaffold copy.
- [x] PyPI release workflow with Trusted Publishing.
- [x] Multi-arch (`linux/amd64`, `linux/arm64`) Docker image published to
      GHCR alongside each PyPI release.
- [x] Homebrew formula skeleton (`packaging/homebrew/lighter-mcp.rb`).
- [x] Smithery catalog manifest (`smithery.yaml`).
- [x] Adapter scaffolds shipped inside the wheel via Hatchling
      `force-include`.
- [ ] First PyPI release (`v0.1.0` → `pip install lighter-mcp` works).
- [ ] First GHCR release (`docker pull ghcr.io/iamgoatedaf/lighter-mcp:0.1.0`).
- [ ] `iamgoatedaf/homebrew-tap` repo created with the synced formula.
- [ ] Smithery catalog page approved.
- [ ] Cursor MCP Directory + `mcp.so` listings submitted.
- [ ] One-shot demo screencast (60s) on the README + docs site.

## v0.3 — trust signals

Read order matters: this milestone is what unlocks selling `live` mode to
strangers. Don't ship before it.

- [ ] External security audit of `safety.py`, `confirmations.py`,
      `tools_live.py`, `tools_funds.py`, `installer.py`. Public report linked
      from `SECURITY.md`.
- [ ] Public bug-bounty program (initial pool: $5–10k). Scope: anything that
      lets an agent skip a confirmation, exceed a cap, or read another
      account's keys.
- [ ] Persisted confirmation tokens. Today `ConfirmationStore` is in-memory;
      a process restart between preview and execute drops the token. Persist
      to `~/.lighter/lighter-mcp/confirmations.json` with the same atomic
      write strategy used by the daily-notional ledger.
- [ ] Drawdown circuit-breaker: when daily realized PnL ≤ a configurable
      threshold (default −5%), auto-flip the active mode to `readonly` until
      the next UTC day or an explicit operator unlock.
- [ ] Time-of-day windows: optional `[live].trading_hours_utc` per symbol;
      orders outside the window are denied with a `SafetyError`.
- [ ] Per-symbol cooldown: minimum interval between consecutive orders on the
      same symbol; defends against runaway agent loops.
- [ ] Total-exposure cap: not just daily flow but maximum simultaneous open
      notional, summed across symbols.
- [ ] Sandboxed kit subprocess (`firejail`/`bubblewrap` on Linux, restricted
      env elsewhere): keep a compromised kit from reading `~/.ssh` or
      arbitrary files.

## v0.4 — wow features (new tools, not new wrappers)

These are what make people share the product. Each is a new MCP tool family
implemented on top of the existing primitives, gated by the same modes.

- [ ] `lighter_strategy_grid`, `lighter_strategy_funding_arb`,
      `lighter_strategy_basis`, `lighter_strategy_dca`. Single-call high-level
      strategies that expand into N gated `lighter_live_*` orders with safety
      preserved end-to-end.
- [ ] `lighter_backtest`. Run a strategy spec against historical candles and
      return PnL / drawdown / hit-rate. Forces strategies to be testable
      before they touch live.
- [ ] `lighter_portfolio_risk`. VaR, max drawdown, distance-to-liquidation
      heatmap across symbols.
- [ ] `lighter_intent_parse`. Parse natural-language order intents
      ("long 0.1 BTC at 60k with 5% TP") into a structured tool-call payload
      on the server side; standardizes behavior across LLM providers.
- [ ] `lighter_journal_*`. Capture agent rationale alongside trades —
      independent of the audit log, which captures *what*, not *why*. Built
      for fund / team auditability.
- [ ] Webhook alerts on top of the existing `price_watcher` daemon. Synks for
      Telegram, Discord, Slack, generic webhook.

## v0.5 — developer experience

Surface the existing tool catalog to users and tooling that don't speak
Python.

- [ ] `lighter-mcp schema`: dump JSON Schema for every tool to stdout so
      clients in any language can codegen typed wrappers.
- [ ] `lighter-mcp explain <tool>`: pretty-print one tool's schema, gates,
      and examples.
- [ ] `--dry-run` for every write tool: print the kit subprocess that would
      run, do not execute.
- [ ] Auto-generated TypeScript types published as `@lighter/mcp-types`.
- [ ] VS Code / Cursor extension: status bar, positions, kill switch, alerts
      log. Turns "MCP server running in the background" into a visible
      product.
- [ ] Opt-in telemetry. Version + OS + tool-call counters only — no keys, no
      symbols, no PnL. Without it we are flying blind on adoption.
- [ ] Plugin API. Third-party packs register additional `lighter_ext_*` tools
      (e.g. MEV scanner, options data). Turns the project into a platform.

## v0.6 — venue expansion

The safety machinery is the moat. Cloning it across venues is a 2–3-week task
each and turns lighter-mcp into an MCP standard for DEX trading rather than a
single-exchange wrapper.

- [ ] Rename `lighter_mcp.safety` → `dex_mcp.safety` (or similar) without
      breaking the public package import path.
- [ ] `hyperliquid-mcp`: same gates, same modes, second adapter.
- [ ] Shared safety primitives extracted to a small reusable package.

## v1.0 — productization

Open-source core stays MIT. Hosted layers add a business model.

- [ ] Hosted Lighter Copilot. One-time pairing code → agent now has Lighter
      tools without local install. Per-call billing.
- [ ] Team / Fund tier. Multiple accounts under a single safety policy with
      RBAC and shared audit log.
- [ ] Mobile companion. Push notifications for live trades + remote
      kill-switch from the phone.
- [ ] Strategy marketplace. Vetted SKILL packages built on
      `lighter_strategy_*`, distributed and versioned.

## Community / non-code

These don't go through PRs but matter for "everyone uses it".

- [ ] Discord with channels per agent platform.
- [ ] Public weekly changelog (newsletter).
- [ ] Strategy gallery: community-submitted SKILLs for `lighter_strategy_*`.
- [ ] Public paper-trading scoreboard (opt-in, ranks pseudonymous accounts
      using lighter-mcp).
- [ ] Comparison page vs. raw kit, Hyperliquid alternatives, etc.
- [ ] Twitter/X account that *uses* the tool to publish daily funding-rate
      digests — best dogfood you can do.

## Out of scope

Things explicitly not on the roadmap, with the reason. Reopen via issue if
context changes.

- **GUI dashboard for end users**: the project is for *agents*. Humans get a
  CLI and a status panel inside their existing agent.
- **Custodial signing service**: the kit owns signing on-device. Hosted
  copilot proxies tool calls but never holds keys.
- **Built-in strategy editor / no-code builder**: out of scope until/unless
  v0.4 strategy primitives clearly under-serve real users.
- **Cross-chain bridges**: Lighter is the surface; bridging is upstream-of-us
  by design.
