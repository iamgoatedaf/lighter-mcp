# Generic MCP integration

See [`adapters/generic/README.md`](../../adapters/generic/README.md) for
install. Any agent that speaks MCP can drive `lighter-mcp`.

## Supported transports

- `stdio` (default). The agent spawns the server as a subprocess.
- `streamable-http` (optional, install with `lighter-mcp[http]`). The server
  binds to `127.0.0.1:<port>` and the agent connects over HTTP.

## Capability discovery

After the standard MCP `initialize` handshake, call `tools/list` to get the
catalog with descriptions and input schemas. Tool names are stable across
modes; only the *availability* changes.

## Implementing the safety contract on the agent side

Every agent must:

1. Call `lighter_safety_status` before any non-trivial workflow.
2. For each `lighter_live_*` and `lighter_funds_*` tool: handle the
   `stage: "preview"` envelope, pass the plan to the user verbatim, and only
   replay with `confirmation_id` after explicit approval.
3. Treat `category: "safety"` and `category: "confirmation"` errors as
   terminal — surface the message, never retry with altered args.
