"""Tool registration must be gated by mode.

In ``readonly`` mode, no paper or live tools should be visible. In ``paper``,
paper tools appear. In ``live``, live tools appear. In ``funds``, the funds
family appears as well.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from lighter_mcp.config import Config, FundsConfig, LiveConfig
from lighter_mcp.server import build_app


def _config(kit_path: Path, tmp_path: Path, mode: str) -> Config:
    return Config(
        mode=mode,  # type: ignore[arg-type]
        kit_path=kit_path,
        audit_log=tmp_path / "audit.jsonl",
        live=LiveConfig(enabled=True, allowed_symbols=("BTC",), max_order_notional_usd=10),
        funds=FundsConfig(transfers_enabled=True, withdrawals_enabled=True, max_withdrawal_usd=10),
    )


async def _names(app) -> set[str]:
    return {t.name for t in await app.list_tools()}


def _has(names: Iterable[str], prefix: str) -> bool:
    return any(n.startswith(prefix) for n in names)


@pytest.mark.asyncio
async def test_readonly_mode_only_exposes_reads(kit_path: Path, tmp_path: Path) -> None:
    app, _ = build_app(_config(kit_path, tmp_path, "readonly"))
    names = await _names(app)
    assert _has(names, "lighter_market_")
    assert "lighter_health" in names
    assert not _has(names, "lighter_paper_")
    assert not _has(names, "lighter_live_")
    assert not _has(names, "lighter_funds_")


@pytest.mark.asyncio
async def test_paper_mode_adds_paper_tools(kit_path: Path, tmp_path: Path) -> None:
    app, _ = build_app(_config(kit_path, tmp_path, "paper"))
    names = await _names(app)
    assert _has(names, "lighter_paper_")
    assert not _has(names, "lighter_live_")
    assert not _has(names, "lighter_funds_")


@pytest.mark.asyncio
async def test_live_mode_adds_live_tools(kit_path: Path, tmp_path: Path) -> None:
    app, _ = build_app(_config(kit_path, tmp_path, "live"))
    names = await _names(app)
    assert _has(names, "lighter_paper_")
    assert _has(names, "lighter_live_")
    assert "lighter_live_limit_order" in names
    assert "lighter_live_close_all" in names
    assert not _has(names, "lighter_funds_")


@pytest.mark.asyncio
async def test_funds_mode_adds_funds_tools(kit_path: Path, tmp_path: Path) -> None:
    app, _ = build_app(_config(kit_path, tmp_path, "funds"))
    names = await _names(app)
    assert _has(names, "lighter_paper_")
    assert _has(names, "lighter_live_")
    assert "lighter_funds_withdraw" in names
    assert "lighter_funds_transfer" in names
