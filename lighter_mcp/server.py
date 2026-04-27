"""Lighter MCP server entrypoint.

Usage:
    lighter-mcp stdio                        # default for local agents
    lighter-mcp serve --host 127.0.0.1 --port 8791
    lighter-mcp doctor                       # smoke-check kit + config
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import __version__
from .audit import AuditLog
from .config import Config, ConfigError, load_config
from .confirmations import ConfirmationStore
from .runner import KitRunner, RunnerError
from .safety import Safety
from .tools_funds import register_funds_tools
from .tools_live import register_live_tools
from .tools_paper import register_paper_tools
from .tools_read import register_read_tools

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


class ServerContext:
    """Plumbing shared by all tool implementations."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.runner = KitRunner(config)
        self.audit = AuditLog(config.audit_log)
        # Persist daily-notional state next to the audit log so caps survive restarts.
        daily_state = config.audit_log.expanduser().parent / "daily-notional.json"
        self.safety = Safety(config, daily_state_path=daily_state)
        self.confirmations = ConfirmationStore(ttl_s=config.confirmation_ttl_s)

    async def run_kit(
        self,
        *,
        tool: str,
        script: str,
        args: list[str],
    ) -> dict[str, Any] | list[Any]:
        """Run a kit script with full audit envelope.

        Always emits an audit record (success or failure). Wraps RunnerError
        into a JSON-serializable error dict so the MCP tool can return it as
        structured content rather than raising.
        """
        try:
            result = await self.runner.run(script, args)
        except RunnerError as exc:
            self.audit.append(
                tool=tool,
                mode=self.config.mode,
                args={"script": script, "argv": args},
                result=None,
                ok=False,
                error=str(exc),
            )
            return exc.to_payload()

        self.audit.append(
            tool=tool,
            mode=self.config.mode,
            args={"script": script, "argv": args},
            result=result.data,
            ok=True,
        )
        return result.data


def build_app(config: Config) -> tuple[FastMCP, ServerContext]:
    ctx = ServerContext(config)
    app = FastMCP(
        name="lighter",
        instructions=(
            "Lighter trading toolkit for AI agents. Tools are grouped by risk: "
            "lighter_market_*/lighter_account_* are read-only, lighter_paper_* are "
            "simulated, lighter_live_* and lighter_funds_* hit the real exchange and "
            "require explicit live/funds mode plus two-step confirmation for high-risk "
            "actions. Read SKILL.md for the complete workflow."
        ),
    )

    # Diagnostic tools (always available).
    @app.tool(
        name="lighter_health",
        description=(
            "Combined health check: kit reachability, system status from Lighter, "
            "and local credential availability. Safe to run in any mode."
        ),
    )
    async def lighter_health() -> dict[str, Any]:
        system = await ctx.run_kit(
            tool="lighter_health",
            script="query.py",
            args=["system", "status"],
        )
        auth = await ctx.run_kit(
            tool="lighter_health",
            script="query.py",
            args=["auth", "status"],
        )
        return {
            "version": __version__,
            "mode": ctx.config.mode,
            "host": ctx.config.host,
            "kit_path": str(ctx.config.kit_path),
            "kit_python": str(ctx.runner.python),
            "audit_log": str(ctx.audit.path),
            "system": system,
            "auth": auth,
        }

    @app.tool(
        name="lighter_version",
        description="Return the lighter-mcp package version and active config summary.",
    )
    def lighter_version() -> dict[str, Any]:
        return {
            "version": __version__,
            "mode": ctx.config.mode,
            "kit_path": str(ctx.config.kit_path),
            "host": ctx.config.host,
            "config_source": str(ctx.config.source_path) if ctx.config.source_path else None,
            "safety": ctx.safety.snapshot(),
        }

    @app.tool(
        name="lighter_safety_status",
        description=(
            "Active mode, allowlists, and remaining daily notional budget. "
            "Useful for the agent to decide whether a write is permitted."
        ),
    )
    def lighter_safety_status() -> dict[str, Any]:
        return ctx.safety.snapshot()

    # Tool families registered by mode. Read-only tools are always present;
    # higher-risk families are gated and added only when the mode allows.
    register_read_tools(app, ctx)
    if ctx.config.mode in ("paper", "live", "funds"):
        register_paper_tools(app, ctx)
    if ctx.config.mode in ("live", "funds"):
        register_live_tools(app, ctx)
    if ctx.config.mode == "funds":
        register_funds_tools(app, ctx)

    return app, ctx


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lighter-mcp",
        description="Lighter MCP server — portable trading tools for MCP-capable agents.",
    )
    parser.add_argument(
        "--config",
        help=(
            "Path to a TOML config file. Defaults to $LIGHTER_MCP_CONFIG, "
            "then ~/.lighter/lighter-mcp/config.toml."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stdio", help="Run on stdio (default for local agents).")

    serve = sub.add_parser("serve", help="Run on Streamable HTTP for daemon use.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8791)
    serve.add_argument(
        "--allow-remote",
        action="store_true",
        help=(
            "Allow binding on a non-loopback address. The MCP server has no "
            "built-in auth, so only enable this when fronting it with a "
            "TLS-terminating reverse proxy that enforces authentication."
        ),
    )

    sub.add_parser(
        "doctor",
        help="Run a non-interactive smoke check (config load + kit health) and exit.",
    )

    init = sub.add_parser(
        "init",
        help=(
            "First-time setup: auto-install the kit, write a default config, "
            "and wire any detected MCP-capable agents (Cursor / Claude / Codex)."
        ),
    )
    from .installer import add_init_args  # local import: keeps import light for stdio runs

    add_init_args(init)

    watch = sub.add_parser(
        "watch",
        help=(
            "Run the price-alert watcher daemon. Polls market stats and emits "
            "edge-triggered notifications when prices cross configured thresholds."
        ),
    )
    watch.add_argument(
        "--alerts",
        help=(
            "Path to a TOML alerts file. Defaults to "
            "~/.lighter/lighter-mcp/price-alerts.toml."
        ),
    )
    watch.add_argument(
        "--once",
        action="store_true",
        help="Run a single check and exit (useful for cron/launchd one-shots).",
    )

    sub.add_parser("version", help="Print the lighter-mcp version and exit.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_argparser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(__version__)
        return 0

    if args.command == "init":
        # ``init`` is the bootstrap command — it must run *before* a valid
        # config exists, so we deliberately don't load_config() here.
        from .installer import run_init_cli

        return run_init_cli(args)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        _print_err(f"config error: {exc}")
        return 2

    if args.command == "doctor":
        return _run_doctor(config)

    if args.command == "watch":
        from .price_watcher import AlertsConfigError, run_watch_cli

        try:
            return run_watch_cli(
                config_path=args.config,
                alerts_path=args.alerts,
                once=args.once,
            )
        except AlertsConfigError as exc:
            _print_err(f"alerts config error: {exc}")
            return 2

    app, _ = build_app(config)

    if args.command == "stdio":
        from .transports.stdio import run_stdio

        run_stdio(app)
        return 0

    if args.command == "serve":
        try:
            from .transports.http import run_http
        except ImportError as exc:
            _print_err(
                f"streamable-http transport unavailable: {exc}. "
                "Install with: pip install 'lighter-mcp[http]'"
            )
            return 2
        run_http(
            app, host=args.host, port=args.port, allow_remote=args.allow_remote
        )
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2  # pragma: no cover


def _run_doctor(config: Config) -> int:
    """Synchronous smoke check usable from the installer."""
    import asyncio

    async def go() -> dict[str, Any]:
        runner = KitRunner(config)
        try:
            result = await runner.run("query.py", ["system", "status"], timeout_s=15.0)
        except RunnerError as exc:
            return {"ok": False, "error": exc.to_payload()}
        return {
            "ok": True,
            "mode": config.mode,
            "kit_path": str(config.kit_path),
            "host": config.host,
            "audit_log": str(config.audit_log.expanduser()),
            "config_source": str(config.source_path) if config.source_path else None,
            "system": result.data,
        }

    payload = asyncio.run(go())
    print(json.dumps(payload, indent=2, default=str))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
