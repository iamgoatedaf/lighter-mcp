"""Tests for safety gates and daily notional accounting."""

from __future__ import annotations

from pathlib import Path

import pytest

from lighter_mcp.config import Config, FundsConfig, LiveConfig
from lighter_mcp.safety import Safety, SafetyError


def _safety(
    tmp_path: Path,
    *,
    mode: str = "live",
    live: LiveConfig | None = None,
    funds: FundsConfig | None = None,
) -> Safety:
    cfg = Config(
        mode=mode,  # type: ignore[arg-type]
        kit_path=Path("/tmp"),
        audit_log=tmp_path / "audit.jsonl",
        live=live or LiveConfig(),
        funds=funds or FundsConfig(),
    )
    return Safety(cfg, daily_state_path=tmp_path / "daily.json")


def test_live_blocked_in_readonly_mode(tmp_path: Path) -> None:
    s = _safety(tmp_path, mode="readonly", live=LiveConfig(enabled=True))
    with pytest.raises(SafetyError, match="not allowed in mode"):
        s.require_live_enabled()


def test_live_blocked_when_disabled(tmp_path: Path) -> None:
    s = _safety(tmp_path, live=LiveConfig(enabled=False))
    with pytest.raises(SafetyError, match="live.enabled"):
        s.require_live_enabled()


def test_symbol_allowlist_enforced(tmp_path: Path) -> None:
    s = _safety(
        tmp_path,
        live=LiveConfig(enabled=True, allowed_symbols=("BTC", "ETH")),
    )
    s.check_symbol_allowed("BTC")
    s.check_symbol_allowed("ETH/USDC")  # base symbol matches
    with pytest.raises(SafetyError):
        s.check_symbol_allowed("DOGE")


def test_symbol_allowlist_empty_allows_all(tmp_path: Path) -> None:
    s = _safety(tmp_path, live=LiveConfig(enabled=True, allowed_symbols=()))
    s.check_symbol_allowed("DOGE")  # no exception


def test_leverage_cap(tmp_path: Path) -> None:
    s = _safety(tmp_path, live=LiveConfig(enabled=True, max_leverage=5))
    s.check_leverage(3)
    with pytest.raises(SafetyError):
        s.check_leverage(10)


def test_order_notional_cap(tmp_path: Path) -> None:
    s = _safety(tmp_path, live=LiveConfig(enabled=True, max_order_notional_usd=100))
    s.check_order_notional(50)
    with pytest.raises(SafetyError):
        s.check_order_notional(200)


def test_daily_room_and_recording(tmp_path: Path) -> None:
    s = _safety(tmp_path, live=LiveConfig(enabled=True, max_daily_notional_usd=100))
    s.check_daily_room(60)
    s.record_executed_notional(60)
    s.check_daily_room(40)
    with pytest.raises(SafetyError):
        s.check_daily_room(50)


def test_daily_state_persists_across_instances(tmp_path: Path) -> None:
    s1 = _safety(tmp_path, live=LiveConfig(enabled=True, max_daily_notional_usd=100))
    s1.record_executed_notional(70)
    s2 = _safety(tmp_path, live=LiveConfig(enabled=True, max_daily_notional_usd=100))
    assert s2.daily_used_usd == pytest.approx(70.0)


def test_corrupt_daily_state_does_not_silently_reset(tmp_path: Path) -> None:
    """A torn write must not silently reset the daily counter to zero.

    Previously a kill mid-_persist() left a truncated JSON; on next load the
    file failed to parse and the cap silently reset to zero. We now quarantine
    the bad file and conservatively report cap-exhausted (inf used).
    """
    state_path = tmp_path / "daily.json"
    state_path.write_text('{"day": "2025-')  # truncated mid-write
    s = _safety(
        tmp_path,
        live=LiveConfig(enabled=True, max_daily_notional_usd=100),
    )
    # Cap should be exhausted, not reset.
    with pytest.raises(SafetyError, match="daily notional cap"):
        s.check_daily_room(1.0)
    # And the corrupt file should be moved aside.
    assert (tmp_path / "daily.json.corrupt").is_file()


def test_atomic_persist_no_truncation(tmp_path: Path) -> None:
    """Successful writes always replace the file atomically."""
    s = _safety(tmp_path, live=LiveConfig(enabled=True, max_daily_notional_usd=1000))
    s.record_executed_notional(50)
    state_path = tmp_path / "daily.json"
    body = state_path.read_text()
    # File is full JSON, not partial.
    import json as _json

    parsed = _json.loads(body)
    assert parsed["notional_usd"] == 50.0


def test_funds_gates(tmp_path: Path) -> None:
    s = _safety(
        tmp_path,
        mode="funds",
        live=LiveConfig(enabled=True),
        funds=FundsConfig(
            transfers_enabled=False,
            withdrawals_enabled=True,
            max_withdrawal_usd=100,
        ),
    )
    with pytest.raises(SafetyError, match="transfers_enabled"):
        s.require_transfers_enabled()
    s.require_withdrawals_enabled()
    s.check_withdrawal_amount_usd(50)
    with pytest.raises(SafetyError):
        s.check_withdrawal_amount_usd(200)
