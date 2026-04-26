"""End-to-end tests of live tools' safety wiring.

These tests patch the ``KitRunner`` so we can drive live tool handlers without
hitting real Lighter APIs, then assert that:

- modify_order enforces the daily notional cap (audit #1).
- modify_order records executed notional on success (audit #15).
- market_order fail-closes when price feed is unavailable (audit #2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lighter_mcp.config import Config, FundsConfig, LiveConfig
from lighter_mcp.runner import RunResult
from lighter_mcp.server import build_app


def _live_config(kit_path: Path, tmp_path: Path, **live_kw: Any) -> Config:
    defaults: dict[str, Any] = dict(
        enabled=True,
        allowed_symbols=("BTC",),
        max_order_notional_usd=10_000,
        max_daily_notional_usd=100,
        max_leverage=10,
        require_confirmation=False,
    )
    defaults.update(live_kw)
    return Config(
        mode="live",
        kit_path=kit_path,
        audit_log=tmp_path / "audit.jsonl",
        live=LiveConfig(**defaults),
        funds=FundsConfig(),
    )


class _FakeRunner:
    """Minimal stand-in for KitRunner."""

    def __init__(self, response: dict | list, *, scripted: dict | None = None) -> None:
        self.response = response
        self.scripted = scripted or {}
        self.calls: list[tuple[str, list[str]]] = []

    @property
    def python(self) -> Path:
        return Path("/usr/bin/python3")

    async def run(self, script: str, args: list[str], *, timeout_s: float = 60.0) -> RunResult:
        self.calls.append((script, list(args)))
        # Allow per-call scripted responses keyed by joined argv.
        key = " ".join(args)
        data = self.scripted.get(key, self.response)
        return RunResult(data=data, raw_stdout="", argv=[script, *args])


@pytest.mark.asyncio
async def test_modify_order_blocked_by_daily_cap(kit_path: Path, tmp_path: Path) -> None:
    """modify_order with notional > daily room must return a safety envelope."""
    cfg = _live_config(kit_path, tmp_path, max_daily_notional_usd=100)
    app, ctx = build_app(cfg)
    ctx.runner = _FakeRunner({"ok": True})  # type: ignore[assignment]
    # Burn most of the daily budget on a recorded prior fill.
    ctx.safety.record_executed_notional(80)

    payload = await app._tool_manager.call_tool(
        "lighter_live_modify_order",
        {
            "input": {
                "symbol": "BTC",
                "order_index": 1,
                "price": 50.0,
                "amount": 1.0,  # notional = 50, daily room left = 20
            }
        },
    )
    assert payload["ok"] is False
    assert payload["category"] == "safety"
    assert "daily" in payload["error"].lower()
    # And the runner was never called.
    assert ctx.runner.calls == []  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_modify_order_records_executed_notional(
    kit_path: Path, tmp_path: Path
) -> None:
    cfg = _live_config(kit_path, tmp_path, max_daily_notional_usd=1_000)
    app, ctx = build_app(cfg)
    ctx.runner = _FakeRunner({"order_index": 7, "status": "modified"})  # type: ignore[assignment]

    before = ctx.safety.daily_used_usd
    payload = await app._tool_manager.call_tool(
        "lighter_live_modify_order",
        {
            "input": {
                "symbol": "BTC",
                "order_index": 1,
                "price": 100.0,
                "amount": 1.5,  # notional = 150
            }
        },
    )
    assert "error" not in payload, payload
    assert ctx.safety.daily_used_usd == pytest.approx(before + 150.0)


@pytest.mark.asyncio
async def test_market_order_fail_closed_when_price_unknown(
    kit_path: Path, tmp_path: Path
) -> None:
    cfg = _live_config(kit_path, tmp_path)
    app, ctx = build_app(cfg)

    # Price probe path returns no usable price (empty stats response).
    runner = _FakeRunner(
        response={"ok": True},
        scripted={"market stats --symbol BTC": []},
    )
    ctx.runner = runner  # type: ignore[assignment]

    payload = await app._tool_manager.call_tool(
        "lighter_live_market_order",
        {"input": {"symbol": "BTC", "side": "buy", "amount": 1.0}},
    )
    assert payload["ok"] is False
    assert payload["category"] == "safety"
    assert "fail-closed" in payload["error"]
    # Only the price probe should have been called; the trade.py invocation
    # must NOT happen.
    scripts = [c[0] for c in runner.calls]
    assert "trade.py" not in scripts
