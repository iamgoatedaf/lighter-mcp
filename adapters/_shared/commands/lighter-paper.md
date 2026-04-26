---
name: lighter-paper
description: Switch the lighter-mcp server into paper-trading mode. Reload required.
---

# /lighter-paper

The lighter-mcp config lives at `~/.lighter/lighter-mcp/config.toml`.
Mode is the first-line `mode = "<readonly|paper|live|funds>"`.

Steps:

1. Tell the user you are about to switch the active config to `paper`. List
   what that changes:
    - paper trading tools become available (`lighter_paper_*`).
    - live trading tools are de-registered (no `lighter_live_*` calls
      possible until the user re-enables `live` later).
    - safety state is preserved on disk; daily notional ledger is unchanged.
2. Wait for the user to confirm in plain language.
3. Update the config file. Use a small shell snippet:

    ```bash
    python3 -c '
    import os, re, pathlib
    p = pathlib.Path(os.path.expanduser("~/.lighter/lighter-mcp/config.toml"))
    s = p.read_text()
    s = re.sub(r"^mode\s*=\s*\".*\"", "mode = \"paper\"", s, count=1, flags=re.MULTILINE)
    p.write_text(s)
    print("ok")
    '
    ```

4. Tell the user to reload the lighter MCP server in their agent (Cursor:
   "Reload MCP servers"; Claude Desktop: restart the app; Codex: re-run the
   plugin install or `/mcp reload`). The new mode takes effect after reload.
5. After reload, suggest running `/lighter-status` to confirm the active
   mode is now `paper`.

If the user wanted a *different* mode (live, funds, readonly), do **not**
silently switch to paper — ask which mode they meant and abort.
