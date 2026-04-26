"""Safety gates and per-day notional accounting.

The gates here are *physical*: write tools are only registered with the MCP
app when the active mode allows them (see ``server.py``). The Safety object
adds a second layer of per-call checks — symbol allowlist, leverage cap,
per-order notional cap, daily aggregate notional cap.

Daily notional state is persisted to a small JSON file alongside the audit
log so caps survive restarts.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Config


class SafetyError(RuntimeError):
    """Raised when an action is denied by mode or risk limits."""


@dataclass
class _DailyState:
    day: str
    notional_usd: float


class DailyNotional:
    """Persisted accumulator of executed live notional per UTC day."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    def _today(self) -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def _load(self) -> _DailyState:
        if self._path.is_file():
            try:
                raw = json.loads(self._path.read_text())
                if raw.get("day") == self._today():
                    return _DailyState(day=raw["day"], notional_usd=float(raw["notional_usd"]))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                # Corrupt or partial file from a prior crash. We deliberately do
                # NOT silently reset to zero — that would mask a state loss and
                # let the agent burn through a fresh daily budget. Rename the
                # bad file aside and conservatively return cap-exhausted state
                # for today so the caller has to investigate.
                quarantine = self._path.with_suffix(self._path.suffix + ".corrupt")
                try:
                    self._path.replace(quarantine)
                except OSError:
                    pass
                return _DailyState(day=self._today(), notional_usd=float("inf"))
        return _DailyState(day=self._today(), notional_usd=0.0)

    def _persist(self) -> None:
        # Atomic write: tempfile in the same directory, fsync, then rename.
        # An os-level kill between any of these steps leaves the previous
        # file intact rather than truncated.
        payload = json.dumps(
            {"day": self._state.day, "notional_usd": self._state.notional_usd}
        ).encode("utf-8")
        directory = self._path.parent
        fd, tmp_path = tempfile.mkstemp(prefix=".dn-", dir=directory)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, self._path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def reset_if_new_day(self) -> None:
        today = self._today()
        if self._state.day != today:
            self._state = _DailyState(day=today, notional_usd=0.0)
            self._persist()

    def value(self) -> float:
        self.reset_if_new_day()
        return self._state.notional_usd

    def add(self, notional_usd: float) -> None:
        self.reset_if_new_day()
        self._state.notional_usd += abs(notional_usd)
        self._persist()


class Safety:
    """Stateless per-call validators plus a stateful daily-notional ledger."""

    def __init__(self, config: Config, daily_state_path: str | os.PathLike[str]) -> None:
        self._config = config
        self._daily = DailyNotional(daily_state_path)

    @property
    def daily_used_usd(self) -> float:
        return self._daily.value()

    @property
    def daily_remaining_usd(self) -> float:
        cap = self._config.live.max_daily_notional_usd
        if cap <= 0:
            return float("inf")
        return max(0.0, cap - self._daily.value())

    # ---- Live trading checks -------------------------------------------

    def require_live_enabled(self) -> None:
        if self._config.mode not in ("live", "funds"):
            raise SafetyError(
                f"live trading not allowed in mode={self._config.mode!r}; "
                "set mode = 'live' in your config."
            )
        if not self._config.live.enabled:
            raise SafetyError(
                "live.enabled=false in config; set it to true to permit live writes."
            )

    def check_symbol_allowed(self, symbol: str) -> None:
        allow = self._config.live.allowed_symbols
        if not allow:
            return
        # Compare by base-symbol prefix so 'BTC' allows 'BTC' or 'BTC/USDC'.
        head = symbol.upper().split("/")[0]
        if head not in allow:
            raise SafetyError(
                f"symbol {symbol!r} not in live.allowed_symbols={list(allow)}"
            )

    def check_leverage(self, leverage: int) -> None:
        cap = self._config.live.max_leverage
        if cap and leverage > cap:
            raise SafetyError(
                f"leverage {leverage} exceeds live.max_leverage={cap}"
            )

    def check_order_notional(self, notional_usd: float) -> None:
        cap = self._config.live.max_order_notional_usd
        if cap and abs(notional_usd) > cap:
            raise SafetyError(
                f"order notional ${notional_usd:.2f} exceeds "
                f"live.max_order_notional_usd=${cap:.2f}"
            )

    def check_daily_room(self, notional_usd: float) -> None:
        cap = self._config.live.max_daily_notional_usd
        if not cap:
            return
        used = self._daily.value()
        if used + abs(notional_usd) > cap:
            raise SafetyError(
                f"order would exceed daily notional cap (used ${used:.2f}, "
                f"cap ${cap:.2f}, this order ${abs(notional_usd):.2f})"
            )

    def record_executed_notional(self, notional_usd: float) -> None:
        self._daily.add(notional_usd)

    # ---- Funds checks --------------------------------------------------

    def require_transfers_enabled(self) -> None:
        self.require_live_enabled()
        if not self._config.funds.transfers_enabled:
            raise SafetyError("funds.transfers_enabled=false in config.")

    def require_withdrawals_enabled(self) -> None:
        self.require_live_enabled()
        if not self._config.funds.withdrawals_enabled:
            raise SafetyError("funds.withdrawals_enabled=false in config.")

    def check_withdrawal_amount_usd(self, amount_usd: float) -> None:
        cap = self._config.funds.max_withdrawal_usd
        if cap and abs(amount_usd) > cap:
            raise SafetyError(
                f"withdrawal ${amount_usd:.2f} exceeds funds.max_withdrawal_usd=${cap:.2f}"
            )

    # ---- Reporting -----------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return {
            "mode": self._config.mode,
            "live": {
                "enabled": self._config.live.enabled,
                "allowed_symbols": list(self._config.live.allowed_symbols),
                "max_order_notional_usd": self._config.live.max_order_notional_usd,
                "max_daily_notional_usd": self._config.live.max_daily_notional_usd,
                "max_leverage": self._config.live.max_leverage,
                "require_confirmation": self._config.live.require_confirmation,
                "daily_used_usd": self._daily.value(),
                "daily_remaining_usd": self.daily_remaining_usd,
            },
            "funds": {
                "transfers_enabled": self._config.funds.transfers_enabled,
                "withdrawals_enabled": self._config.funds.withdrawals_enabled,
                "max_withdrawal_usd": self._config.funds.max_withdrawal_usd,
                "require_confirmation": self._config.funds.require_confirmation,
            },
        }
