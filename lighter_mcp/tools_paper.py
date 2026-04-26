"""Paper trading MCP tools.

Wrap ``scripts/paper.py`` from the kit. Paper trading runs entirely locally
against live order-book snapshots from Lighter and never broadcasts anything,
so these tools have no risk gates beyond input validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .schemas import (
    PaperLiquidationInput,
    PaperOrderIocInput,
    PaperOrderMarketInput,
    PaperPositionsInput,
    PaperSetTierInput,
    PaperTradesInput,
    SymbolInput,
)

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP

    from .server import ServerContext


def register_paper_tools(app: FastMCP, ctx: ServerContext) -> None:
    @app.tool(
        name="lighter_paper_init",
        description="Create a new paper trading account. Required before the first paper order.",
    )
    async def lighter_paper_init() -> Any:
        return await ctx.run_kit(
            tool="lighter_paper_init", script="paper.py", args=["init"]
        )

    @app.tool(
        name="lighter_paper_reset",
        description="Wipe paper state and start fresh. Confirms by overwriting state.",
    )
    async def lighter_paper_reset() -> Any:
        return await ctx.run_kit(
            tool="lighter_paper_reset", script="paper.py", args=["reset"]
        )

    @app.tool(
        name="lighter_paper_set_tier",
        description="Change paper account fee tier. Choices: standard, premium, premium_1..premium_7.",
    )
    async def lighter_paper_set_tier(input: PaperSetTierInput) -> Any:
        return await ctx.run_kit(
            tool="lighter_paper_set_tier",
            script="paper.py",
            args=["set_tier", "--tier", input.tier],
        )

    @app.tool(
        name="lighter_paper_status",
        description="Paper account summary: equity, margin, fees.",
    )
    async def lighter_paper_status() -> Any:
        return await ctx.run_kit(
            tool="lighter_paper_status", script="paper.py", args=["status"]
        )

    @app.tool(
        name="lighter_paper_positions",
        description="Open paper positions. Use no_refresh to skip live snapshot fetch.",
    )
    async def lighter_paper_positions(input: PaperPositionsInput) -> Any:
        args = ["positions"]
        if input.symbol:
            args += ["--symbol", input.symbol]
        if input.no_refresh:
            args += ["--no-refresh"]
        return await ctx.run_kit(
            tool="lighter_paper_positions", script="paper.py", args=args
        )

    @app.tool(
        name="lighter_paper_trades",
        description="Paper trade history (most recent first).",
    )
    async def lighter_paper_trades(input: PaperTradesInput) -> Any:
        args = ["trades", "--limit", str(input.limit)]
        if input.symbol:
            args += ["--symbol", input.symbol]
        return await ctx.run_kit(
            tool="lighter_paper_trades", script="paper.py", args=args
        )

    @app.tool(
        name="lighter_paper_health",
        description="Paper account health and margin status.",
    )
    async def lighter_paper_health() -> Any:
        return await ctx.run_kit(
            tool="lighter_paper_health", script="paper.py", args=["health"]
        )

    @app.tool(
        name="lighter_paper_liquidation_price",
        description="Estimated liquidation price for a paper position.",
    )
    async def lighter_paper_liquidation_price(input: PaperLiquidationInput) -> Any:
        args = ["liquidation_price", input.symbol]
        if input.no_refresh:
            args += ["--no-refresh"]
        return await ctx.run_kit(
            tool="lighter_paper_liquidation_price", script="paper.py", args=args
        )

    @app.tool(
        name="lighter_paper_refresh",
        description="Force-refresh order book snapshot for diagnostics.",
    )
    async def lighter_paper_refresh(input: SymbolInput) -> Any:
        return await ctx.run_kit(
            tool="lighter_paper_refresh",
            script="paper.py",
            args=["refresh", input.symbol],
        )

    @app.tool(
        name="lighter_paper_market_order",
        description="Place a taker-only paper market order.",
    )
    async def lighter_paper_market_order(input: PaperOrderMarketInput) -> Any:
        return await ctx.run_kit(
            tool="lighter_paper_market_order",
            script="paper.py",
            args=[
                "order",
                "market",
                input.symbol,
                "--side",
                input.side,
                "--amount",
                str(input.amount),
            ],
        )

    @app.tool(
        name="lighter_paper_ioc_order",
        description="Place a taker-only paper IOC order with a limit price.",
    )
    async def lighter_paper_ioc_order(input: PaperOrderIocInput) -> Any:
        return await ctx.run_kit(
            tool="lighter_paper_ioc_order",
            script="paper.py",
            args=[
                "order",
                "ioc",
                input.symbol,
                "--side",
                input.side,
                "--amount",
                str(input.amount),
                "--price",
                str(input.price),
            ],
        )
