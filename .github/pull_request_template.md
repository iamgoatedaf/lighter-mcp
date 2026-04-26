<!--
Thanks for the PR! Please make sure:
  • All P0/P1 changes have a regression test in tests/
  • You ran `ruff check .` and `pytest -q` locally
  • If you touched safety/confirmation/audit logic, you updated SECURITY.md
  • If you added a tool, you bumped any relevant adapter SKILL.md / sub-agent
-->

## Summary

<!-- One paragraph: what changed, why, and which user-facing surface. -->

## Risk surface

- [ ] read-only / docs / CI only — no behavior change for existing flows
- [ ] paper-only
- [ ] live trading touched (`lighter_live_*`, safety gates, confirmations)
- [ ] funds touched (`lighter_funds_*`)

## Test plan

<!-- How did you verify? -->

- [ ] `pytest -q` passes
- [ ] `ruff check .` passes
- [ ] If integration paths changed: ran `lighter-mcp doctor` and exercised at
      least one tool via stdio
- [ ] If you added a new tool: registered in the right mode block in
      `server.py` and added a row to the README mode/tool matrix

## Backwards compatibility

<!-- Tool name changes, schema changes, config changes? -->

## Linked issues

Closes #
