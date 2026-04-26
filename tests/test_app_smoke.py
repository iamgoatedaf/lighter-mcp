"""Smoke tests for the FastMCP app construction and tool registration.

Network-light: only verifies that tools are registered with the right names
and shapes. Network-bearing tests live in ``test_kit_integration.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lighter_mcp.config import Config, FundsConfig, LiveConfig
from lighter_mcp.server import build_app


@pytest.fixture
def config(kit_path: Path, tmp_path: Path) -> Config:
    return Config(
        mode="readonly",
        kit_path=kit_path,
        audit_log=tmp_path / "audit.jsonl",
        live=LiveConfig(),
        funds=FundsConfig(),
    )


@pytest.mark.asyncio
async def test_tool_catalog_contains_expected_read_tools(config: Config) -> None:
    app, _ = build_app(config)
    tools = await app.list_tools()
    names = {t.name for t in tools}

    expected = {
        "lighter_health",
        "lighter_version",
        "lighter_system_status",
        "lighter_list_markets",
        "lighter_market_stats",
        "lighter_market_info",
        "lighter_market_book",
        "lighter_market_trades",
        "lighter_market_candles",
        "lighter_market_funding",
        "lighter_auth_status",
        "lighter_account_info",
        "lighter_account_apikeys",
        "lighter_account_limits",
        "lighter_portfolio_performance",
        "lighter_orders_open",
        "lighter_orders_history",
    }
    missing = expected - names
    assert not missing, f"missing tools: {missing}"


@pytest.mark.asyncio
async def test_each_tool_has_input_schema(config: Config) -> None:
    app, _ = build_app(config)
    tools = await app.list_tools()
    for t in tools:
        assert t.inputSchema is not None, f"tool {t.name} missing inputSchema"
        assert "type" in t.inputSchema, f"tool {t.name} schema missing type"
