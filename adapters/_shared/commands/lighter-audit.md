---
name: lighter-audit
description: Show recent entries from the lighter-mcp audit log with filters (tool, mode, ok/failed, hours).
---

# /lighter-audit

The audit log lives at `~/.lighter/lighter-mcp/audit.jsonl` (append-only
JSONL, one record per tool call, secrets pre-redacted by the server).

Default behavior: show the last **20** records of the last **24 hours**.

Optional arguments the user might pass in plain language:
- "last N hours" / "since N hours ago"
- "only failures"
- "tool lighter_live_market_order" (or any prefix like `lighter_live_*`)
- "mode live" / "mode paper"

Steps:

1. Parse the user's natural-language filters. Defaults if absent: `hours=24`,
   `limit=20`, no tool/mode filter, all results.
2. Read the log with a small shell snippet (do **not** load the whole file
   into context — it can be large):

    ```bash
    python3 - <<'PY'
    import json, os, time, pathlib
    HOURS = 24       # replace with parsed value
    LIMIT = 20       # replace with parsed value
    TOOL  = None     # e.g. "lighter_live_market_order" or prefix
    MODE  = None     # "live" / "paper" / etc.
    OK    = None     # True for only-success, False for only-failures, None for both
    cutoff = time.time() - HOURS * 3600
    p = pathlib.Path(os.path.expanduser("~/.lighter/lighter-mcp/audit.jsonl"))
    if not p.is_file():
        print("[]"); raise SystemExit
    rows = []
    with p.open() as fh:
        for line in fh:
            try: r = json.loads(line)
            except Exception: continue
            if r.get("ts", 0) < cutoff: continue
            if TOOL and not r.get("tool", "").startswith(TOOL): continue
            if MODE and r.get("mode") != MODE: continue
            if OK is not None and bool(r.get("ok")) != OK: continue
            rows.append(r)
    rows = rows[-LIMIT:]
    print(json.dumps(rows, indent=2))
    PY
    ```

3. Render a compact table: timestamp (local time), tool, mode, ok/error,
   one-line summary of args (symbol/amount where present).
4. If a row has `error`, show the `error` and `category` verbatim — these
   are the safety/confirmation envelopes and they are exactly what the user
   wants to inspect.

Never modify or rotate the audit file from this command.
