# `_shared/` — single source of truth

The slash-command prompts, the `lighter-trader` sub-agent, and the
post-tool-call hook script live here. Per-platform folders
(`cursor/`, `claude/`, `codex/.codex-plugin/`) carry **symlinks** that
point back to these files, so a fix in one place propagates everywhere.

## Layout

```
adapters/_shared/
├── commands/
│   ├── lighter-status.md
│   ├── lighter-positions.md
│   ├── lighter-kill.md
│   ├── lighter-paper.md
│   └── lighter-audit.md
├── agents/
│   └── lighter-trader.md
├── hooks/
│   └── after-lighter-trade.sh
└── sync.sh        ← run this on Windows / when symlinks aren't supported
```

## Windows / symlink-less filesystems

Git for Windows by default does **not** materialize symlinks unless
`core.symlinks=true` is set, so a fresh clone there will leave per-platform
folders with broken text-file "links". Run:

```bash
bash adapters/_shared/sync.sh
```

This replaces the stubs with real file copies. Re-run any time you pull
new changes to `_shared/`.

## Editing rules

- **Always** edit files under `_shared/`. Never edit the per-platform
  copies — your change will be overwritten on next sync.
- Keep prompts platform-agnostic. They are loaded as plain markdown by
  Cursor, Claude Code, and Codex; YAML frontmatter (`name:`,
  `description:`) is read by Claude Code and ignored by the other two.
