"""Run the MCP server over stdio (default transport for local agents)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def run_stdio(app: FastMCP) -> None:
    """Run a FastMCP app on stdio. Blocks until the client disconnects."""
    app.run(transport="stdio")
