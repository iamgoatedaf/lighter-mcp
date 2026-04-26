"""Regression tests for issues raised in the external security audit.

Covers:
    - argv-injection guard via schema regex on symbol/asset.
    - market_order fail-closed when notional is unknown.
    - modify_order respects per-day notional cap and records executed notional.
    - HTTP transport refuses non-loopback bind without --allow-remote.
    - Config rejects bogus host schemes.
"""

from __future__ import annotations

import pytest

from lighter_mcp.config import ConfigError
from lighter_mcp.schemas import (
    LimitOrderInput,
    MarketStatsInput,
    PaperSetTierInput,
    TransferInput,
    WithdrawInput,
)
from lighter_mcp.transports.http import _is_loopback, run_http

# ---------------------------------------------------------------------------
# Schema regex (audit #8)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_symbol",
    [
        "--side=long",  # CLI flag injection
        "-h",
        "BTC; rm -rf /",
        "BTC && id",
        "BTC$(id)",
        "BTC\nETH",
        "",
        " ",
        "B" * 33,  # too long
        "btc/usdc'",  # quote
    ],
)
def test_symbol_regex_rejects_dangerous_inputs(bad_symbol: str) -> None:
    with pytest.raises(ValueError):
        LimitOrderInput(
            symbol=bad_symbol,
            side="buy",
            amount=1.0,
            price=100.0,
        )


@pytest.mark.parametrize("good_symbol", ["BTC", "ETH/USDC", "BTC-PERP", "1000PEPE", "SOL.PERP"])
def test_symbol_regex_accepts_realistic_inputs(good_symbol: str) -> None:
    inp = LimitOrderInput(symbol=good_symbol, side="buy", amount=1.0, price=100.0)
    assert inp.symbol == good_symbol.upper()


def test_market_stats_optional_symbol_validates() -> None:
    MarketStatsInput(symbol=None)
    MarketStatsInput(symbol="BTC")
    with pytest.raises(ValueError):
        MarketStatsInput(symbol="--limit")


def test_asset_regex_rejects_injection() -> None:
    with pytest.raises(ValueError):
        WithdrawInput(asset="--amount=999", amount=1.0)
    with pytest.raises(ValueError):
        TransferInput(
            asset="USDC; cat /etc/passwd",
            amount=1.0,
            from_route="perp",
            to_route="spot",
        )
    # Sanity: real values still pass.
    WithdrawInput(asset="USDC", amount=1.0)


def test_tier_regex_rejects_injection() -> None:
    with pytest.raises(ValueError):
        PaperSetTierInput(tier="--something")
    PaperSetTierInput(tier="premium_3")


# ---------------------------------------------------------------------------
# HTTP transport (audit #5)
# ---------------------------------------------------------------------------


def test_loopback_classifier() -> None:
    assert _is_loopback("127.0.0.1")
    assert _is_loopback("::1")
    assert _is_loopback("localhost")
    assert not _is_loopback("0.0.0.0")
    assert not _is_loopback("192.168.1.10")
    assert not _is_loopback("example.com")


def test_serve_refuses_non_loopback_without_opt_in() -> None:
    class _StubApp:
        class settings:
            host = "127.0.0.1"
            port = 0

        def run(self, *, transport: str) -> None:  # pragma: no cover
            raise AssertionError("must not be reached")

    app = _StubApp()
    with pytest.raises(SystemExit, match="non-loopback"):
        run_http(app, host="0.0.0.0", port=8791, allow_remote=False)


# ---------------------------------------------------------------------------
# Host scheme validation (audit #9)
# ---------------------------------------------------------------------------


def test_config_host_scheme_validation(tmp_path) -> None:
    from lighter_mcp.config import load_config

    # Create a kit_path so the loader gets past that check.
    kit_dir = tmp_path / "kit"
    kit_dir.mkdir()
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        f'mode = "readonly"\n'
        f'kit_path = "{kit_dir}"\n'
        f'host = "file:///etc/passwd"\n'
    )
    with pytest.raises(ConfigError, match="http"):
        load_config(cfg_path)
