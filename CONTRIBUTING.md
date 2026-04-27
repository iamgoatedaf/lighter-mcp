# Contributing to lighter-mcp

Thanks for the interest. This is a small, security-sensitive project, so
the bar for changes that touch live trading or funds movement is high.
Read this end-to-end before opening a PR.

## Quick dev setup

```bash
git clone https://github.com/iamgoatedaf/lighter-mcp
cd lighter-mcp
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev,http]"

# Run the test + lint suite
.venv/bin/ruff check .
.venv/bin/pytest -q
```

Tests that depend on the actual `lighter-agent-kit` checkout are
auto-skipped unless `LIGHTER_KIT_PATH` points at a working clone:

```bash
export LIGHTER_KIT_PATH=/path/to/lighter-agent-kit
pytest -q
```

## What "security-sensitive" means here

- Anything in `lighter_mcp/safety.py`, `confirmations.py`, `audit.py`,
  `transports/http.py`, or the `lighter_live_*` / `lighter_funds_*` tools
  is on the fund-loss path.
- Pull requests touching those files **must**:
    1. Include regression tests under `tests/test_security_audit.py` or
       `tests/test_live_safety_integration.py`.
    2. Update `SECURITY.md` if the threat model changes.
    3. Be reviewed by at least one other maintainer before merge.

## Coding standards

- Python ≥ 3.10, type hints everywhere, `from __future__ import annotations`.
- `ruff` config in `pyproject.toml`. No new lint warnings.
- No new top-level dependencies without discussion in the PR. Optional
  features go behind `[project.optional-dependencies]`.
- All MCP tool inputs go through a Pydantic schema in `schemas.py` with
  strict regex validation for symbols, asset codes, and any string that
  is forwarded to a subprocess.
- Never widen what gets logged. The audit log is **append-only** and
  sanitization rules in `audit.py::_sanitize` are conservative on
  purpose — extend the redaction list rather than narrowing it.

## Style for tool descriptions

- Keep `description=` on `@app.tool` short (one sentence) and explicitly
  call out two-step confirmation for risky tools.
- Tool names are lowercase, prefixed `lighter_<family>_<verb>`.

## Adding a new tool

1. Pick the right module: `tools_read.py`, `tools_paper.py`, `tools_live.py`,
   or `tools_funds.py`.
2. Add a Pydantic input schema in `schemas.py`.
3. If it can move money, route it through `Safety` *and* the
   `_maybe_preview` helper for two-step confirmation.
4. Always run via `ctx.run_kit(...)` — never call subprocesses directly,
   so the audit envelope is consistent.
5. Add a row to the README mode/tool matrix.
6. Add at least one regression test (mode-gating + envelope shape).

## Adding a new agent adapter

1. Create `adapters/<name>/` with a README, an example MCP config, and
   any platform-specific manifest (e.g. `plugin.json`).
2. Symlink (or copy on Windows via `adapters/_shared/sync.sh`) the shared
   commands and agents from `adapters/_shared/`. Don't fork them.
3. If the platform supports hooks, point its post-tool-call hook at
   `adapters/_shared/hooks/after-lighter-trade.sh`.
4. Update the README adapter table.

## Releases

Versions follow SemVer. Patch (`0.1.x`) for bug fixes, minor (`0.x.0`)
for new tools or relaxed schemas, major (`x.0.0`) for any change that
removes a tool, narrows a schema, or alters confirmation semantics.

Cutting a release:

1. Update `lighter_mcp/__init__.py::__version__` and the `pyproject.toml`
   `version` to the new value (keep them in sync).
2. Add a `[X.Y.Z] — YYYY-MM-DD` section to `CHANGELOG.md` summarising the
   public-facing changes.
3. Tag the commit on `main` and push the tag:

   ```bash
   git tag vX.Y.Z && git push origin vX.Y.Z
   ```

   The `release.yml` workflow then builds the sdist + wheel, publishes to
   [PyPI](https://pypi.org/project/lighter-mcp/) via Trusted Publishing,
   pushes a Docker image to `ghcr.io/iamgoatedaf/lighter-mcp:X.Y.Z`, and
   drafts a GitHub Release with the same artifacts attached.

The PyPI publish step requires a maintainer to approve the deployment in
the `pypi` GitHub environment — this is intentional belt-and-suspenders
beyond the OIDC handshake.

## Reporting bugs and vulnerabilities

- Bugs: open an issue using the bug-report template.
- Vulnerabilities: see `SECURITY.md`. Do **not** file public issues for
  anything that lets an agent move funds without confirmation.
