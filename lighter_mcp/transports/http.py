"""Run the MCP server over Streamable HTTP / SSE for daemon use cases."""

from __future__ import annotations

import ipaddress
import sys

from mcp.server.fastmcp import FastMCP

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _is_loopback(host: str) -> bool:
    if host in _LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def run_http(
    app: FastMCP, *, host: str, port: int, allow_remote: bool = False
) -> None:
    """Run a FastMCP app on Streamable HTTP. Requires the ``http`` extras.

    The MCP server has NO built-in authentication. Binding to a non-loopback
    address (e.g. ``0.0.0.0``) on a host with live credentials would expose
    every live trading tool to anyone who can reach the port. We refuse such
    binds unless the operator explicitly opts in via ``allow_remote=True``
    (CLI: ``--allow-remote``).
    """
    if not _is_loopback(host) and not allow_remote:
        raise SystemExit(
            f"refusing to bind streamable-http on non-loopback host {host!r}: "
            "the MCP server has no auth. Use --host 127.0.0.1 for local use, "
            "or pass --allow-remote if you've put it behind a TLS-terminating "
            "reverse proxy with authentication."
        )
    if not _is_loopback(host) and allow_remote:
        print(
            f"WARNING: lighter-mcp is binding on {host}:{port} with no built-in "
            "authentication. Make sure a reverse proxy enforces auth, TLS, and "
            "ACLs before exposing this to the network.",
            file=sys.stderr,
            flush=True,
        )
    app.settings.host = host
    app.settings.port = port
    app.run(transport="streamable-http")
