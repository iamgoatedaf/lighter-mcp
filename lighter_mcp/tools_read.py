"""Read-only MCP tools: market data and authenticated account reads.

Each tool is a thin typed adapter over the kit's ``query.py`` CLI. We translate
pydantic-validated arguments into the kit's argv flags and let the runner
parse the JSON response.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .schemas import (
    AccountInfoInput,
    MarketBookInput,
    MarketCandlesInput,
    MarketFundingInput,
    MarketListInput,
    MarketStatsInput,
    MarketTradesInput,
    OrdersOpenInput,
    PortfolioPerformanceInput,
)

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP

    from .server import ServerContext


def register_read_tools(app: FastMCP, ctx: ServerContext) -> None:
    """Attach all read-only tools to ``app``."""

    @app.tool(
        name="lighter_system_status",
        description="System health and chain status from Lighter. Public read.",
    )
    async def lighter_system_status() -> Any:
        return await ctx.run_kit(
            tool="lighter_system_status",
            script="query.py",
            args=["system", "status"],
        )

    @app.tool(
        name="lighter_list_markets",
        description=(
            "Compact symbol → market_index catalog. Filter by perp/spot or "
            "search substring."
        ),
    )
    async def lighter_list_markets(input: MarketListInput) -> Any:
        args = ["market", "list"]
        if input.market_type:
            args += ["--market_type", input.market_type]
        if input.search:
            args += ["--search", input.search]
        return await ctx.run_kit(
            tool="lighter_list_markets",
            script="query.py",
            args=args,
        )

    @app.tool(
        name="lighter_market_stats",
        description=(
            "Market overview: prices, 24h volumes, funding. Optionally filter "
            "to a single symbol."
        ),
    )
    async def lighter_market_stats(input: MarketStatsInput) -> Any:
        args = ["market", "stats"]
        if input.symbol:
            args += ["--symbol", input.symbol]
        return await ctx.run_kit(
            tool="lighter_market_stats",
            script="query.py",
            args=args,
        )

    @app.tool(
        name="lighter_market_info",
        description="Market metadata: fees, decimals, minimum sizes.",
    )
    async def lighter_market_info(input: MarketStatsInput) -> Any:
        args = ["market", "info"]
        if input.symbol:
            args += ["--symbol", input.symbol]
        return await ctx.run_kit(
            tool="lighter_market_info",
            script="query.py",
            args=args,
        )

    @app.tool(
        name="lighter_market_book",
        description="Top-of-book snapshot (bids/asks) for one market.",
    )
    async def lighter_market_book(input: MarketBookInput) -> Any:
        return await ctx.run_kit(
            tool="lighter_market_book",
            script="query.py",
            args=[
                "market",
                "book",
                input.symbol,
                "--limit",
                str(input.limit),
            ],
        )

    @app.tool(
        name="lighter_market_trades",
        description="Recent fills for one market.",
    )
    async def lighter_market_trades(input: MarketTradesInput) -> Any:
        return await ctx.run_kit(
            tool="lighter_market_trades",
            script="query.py",
            args=[
                "market",
                "trades",
                input.symbol,
                "--limit",
                str(input.limit),
            ],
        )

    @app.tool(
        name="lighter_market_candles",
        description=(
            "OHLCV candles for one market. Resolutions: 1m, 5m, 15m, 30m, "
            "1h, 4h, 1d."
        ),
    )
    async def lighter_market_candles(input: MarketCandlesInput) -> Any:
        return await ctx.run_kit(
            tool="lighter_market_candles",
            script="query.py",
            args=[
                "market",
                "candles",
                input.symbol,
                "--resolution",
                input.resolution,
                "--count_back",
                str(input.count_back),
            ],
        )

    @app.tool(
        name="lighter_market_funding",
        description="Current and recent funding rate for one perpetual market.",
    )
    async def lighter_market_funding(input: MarketFundingInput) -> Any:
        return await ctx.run_kit(
            tool="lighter_market_funding",
            script="query.py",
            args=["market", "funding", "--symbol", input.symbol],
        )

    @app.tool(
        name="lighter_auth_status",
        description="Local credential check: which keys are present without using them.",
    )
    async def lighter_auth_status() -> Any:
        return await ctx.run_kit(
            tool="lighter_auth_status",
            script="query.py",
            args=["auth", "status"],
        )

    @app.tool(
        name="lighter_account_info",
        description=(
            "Public account lookup. With account_index, anyone can read; without, "
            "uses the configured account."
        ),
    )
    async def lighter_account_info(input: AccountInfoInput) -> Any:
        args = ["account", "info"]
        if input.account_index is not None:
            args += ["--account_index", str(input.account_index)]
        return await ctx.run_kit(
            tool="lighter_account_info",
            script="query.py",
            args=args,
        )

    @app.tool(
        name="lighter_account_apikeys",
        description="Public API-key listing for an account index.",
    )
    async def lighter_account_apikeys(input: AccountInfoInput) -> Any:
        args = ["account", "apikeys"]
        if input.account_index is not None:
            args += ["--account_index", str(input.account_index)]
        return await ctx.run_kit(
            tool="lighter_account_apikeys",
            script="query.py",
            args=args,
        )

    @app.tool(
        name="lighter_account_limits",
        description="Authenticated: current trading tier and limits.",
    )
    async def lighter_account_limits() -> Any:
        return await ctx.run_kit(
            tool="lighter_account_limits",
            script="query.py",
            args=["account", "limits"],
        )

    @app.tool(
        name="lighter_portfolio_performance",
        description="Authenticated: PnL series at the chosen resolution.",
    )
    async def lighter_portfolio_performance(input: PortfolioPerformanceInput) -> Any:
        return await ctx.run_kit(
            tool="lighter_portfolio_performance",
            script="query.py",
            args=["portfolio", "performance", "--resolution", input.resolution],
        )

    @app.tool(
        name="lighter_orders_open",
        description="Authenticated: live open orders, optionally filtered by symbol.",
    )
    async def lighter_orders_open(input: OrdersOpenInput) -> Any:
        args = ["orders", "open"]
        if input.symbol:
            args += ["--symbol", input.symbol]
        return await ctx.run_kit(
            tool="lighter_orders_open",
            script="query.py",
            args=args,
        )

    @app.tool(
        name="lighter_orders_history",
        description="Authenticated: past orders for the configured account.",
    )
    async def lighter_orders_history() -> Any:
        return await ctx.run_kit(
            tool="lighter_orders_history",
            script="query.py",
            args=["orders", "history"],
        )
