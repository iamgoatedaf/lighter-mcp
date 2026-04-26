"""Price-alert watcher daemon.

Polls the kit for ``market stats`` on the configured symbols and emits
edge-triggered notifications when prices cross absolute thresholds.

This is intentionally **not** an MCP tool: agents do not call it. It runs
alongside the MCP server (or completely standalone) so the user gets push
alerts even when no chat agent is active.

Run it with ``lighter-mcp watch`` (see ``server.py``).
"""

from __future__ import annotations

import asyncio
import json
import platform
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from .config import Config, load_config
from .runner import KitRunner, RunnerError

DEFAULT_ALERTS_PATH = Path("~/.lighter/lighter-mcp/price-alerts.toml").expanduser()
DEFAULT_STATE_PATH = Path("~/.lighter/lighter-mcp/price-alerts.state.json").expanduser()
DEFAULT_NOTIFY_LOG = Path("~/.lighter/lighter-mcp/notifications.log").expanduser()


@dataclass(frozen=True)
class AlertRule:
    """One edge-triggered threshold rule."""

    symbol: str
    op: str  # "above" or "below"
    price: float
    label: str = ""

    @property
    def key(self) -> str:
        return f"{self.symbol}:{self.op}:{self.price}"


@dataclass
class WatcherConfig:
    interval_s: float = 30.0
    symbols: list[str] = field(default_factory=list)
    rules: list[AlertRule] = field(default_factory=list)
    notify_log: Path = DEFAULT_NOTIFY_LOG
    state_path: Path = DEFAULT_STATE_PATH
    desktop: bool = True


class AlertsConfigError(ValueError):
    """Raised when the alerts TOML file is missing or malformed."""


def load_alerts(path: Path) -> WatcherConfig:
    """Parse an alerts TOML file into a ``WatcherConfig``."""
    if not path.is_file():
        raise AlertsConfigError(
            f"price-alerts file not found: {path}. "
            "Copy mcp/configs/price-alerts.example.toml as a starting point."
        )
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    interval = float(raw.get("interval_s", 30.0))
    if interval < 5:
        raise AlertsConfigError("interval_s must be >= 5 seconds (avoid hammering the API)")

    notify_log = Path(str(raw.get("notify_log", DEFAULT_NOTIFY_LOG))).expanduser()
    state_path = Path(str(raw.get("state_path", DEFAULT_STATE_PATH))).expanduser()
    desktop = bool(raw.get("desktop", True))

    rules_raw = raw.get("alerts", [])
    if not isinstance(rules_raw, list):
        raise AlertsConfigError("[[alerts]] must be a list of tables")

    rules: list[AlertRule] = []
    symbols: set[str] = set()
    for i, item in enumerate(rules_raw):
        if not isinstance(item, dict):
            raise AlertsConfigError(f"alerts[{i}] must be a table")
        try:
            symbol = str(item["symbol"]).upper()
            op = str(item["op"]).lower()
            price = float(item["price"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AlertsConfigError(
                f"alerts[{i}] missing/invalid required field: {exc}"
            ) from exc
        if op not in ("above", "below"):
            raise AlertsConfigError(
                f"alerts[{i}].op must be 'above' or 'below', got {op!r}"
            )
        rules.append(
            AlertRule(
                symbol=symbol,
                op=op,
                price=price,
                label=str(item.get("label", "")),
            )
        )
        symbols.add(symbol)

    return WatcherConfig(
        interval_s=interval,
        symbols=sorted(symbols),
        rules=rules,
        notify_log=notify_log,
        state_path=state_path,
        desktop=desktop,
    )


def load_state(path: Path) -> dict[str, bool]:
    try:
        with path.open() as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): bool(v) for k, v in data.items()}


def save_state(path: Path, state: dict[str, bool]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
    tmp.replace(path)


async def fetch_prices(runner: KitRunner) -> dict[str, float]:
    """Return ``{symbol: last_trade_price}`` from a single ``market stats`` call."""
    res = await runner.run("query.py", ["market", "stats"], timeout_s=20.0)
    if not isinstance(res.data, dict):
        return {}
    rows = res.data.get("order_book_stats")
    if not isinstance(rows, list):
        return {}
    prices: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sym = row.get("symbol")
        px = row.get("last_trade_price")
        if isinstance(sym, str) and isinstance(px, (int, float)) and px > 0:
            prices[sym] = float(px)
    return prices


def evaluate(rule: AlertRule, price: float) -> bool:
    if rule.op == "above":
        return price > rule.price
    return price < rule.price


def notify(message: str, log_path: Path, *, desktop: bool) -> None:
    """Append to log and (optionally) post a macOS desktop notification."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    line = f"{ts} {message}"
    try:
        with log_path.open("a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass
    print(line, flush=True)
    if not desktop:
        return
    if platform.system() != "Darwin" or not shutil.which("osascript"):
        return
    body = message.replace("\\", "\\\\").replace('"', '\\"')
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{body}" with title "Lighter price alert"',
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        pass


async def watch_loop(
    cfg: Config,
    alerts: WatcherConfig,
    *,
    once: bool = False,
) -> int:
    runner = KitRunner(cfg)
    state = load_state(alerts.state_path)
    stop_event = asyncio.Event()

    def _stop(*_: Any) -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    notify(
        f"watcher started: {len(alerts.rules)} rules, "
        f"{len(alerts.symbols)} symbols, every {alerts.interval_s:g}s",
        alerts.notify_log,
        desktop=False,
    )

    while not stop_event.is_set():
        try:
            prices = await fetch_prices(runner)
        except RunnerError as exc:
            notify(f"price fetch error: {exc}", alerts.notify_log, desktop=False)
            prices = {}

        for rule in alerts.rules:
            px = prices.get(rule.symbol)
            if px is None:
                continue
            triggered = evaluate(rule, px)
            prev = state.get(rule.key, False)
            if triggered and not prev:
                arrow = ">" if rule.op == "above" else "<"
                tail = f" [{rule.label}]" if rule.label else ""
                notify(
                    f"{rule.symbol} {arrow} {rule.price:g} (now {px:g}){tail}",
                    alerts.notify_log,
                    desktop=alerts.desktop,
                )
            state[rule.key] = triggered

        try:
            save_state(alerts.state_path, state)
        except OSError as exc:
            notify(f"state save error: {exc}", alerts.notify_log, desktop=False)

        if once:
            break

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=alerts.interval_s)
        except asyncio.TimeoutError:
            pass

    notify("watcher stopped", alerts.notify_log, desktop=False)
    return 0


def run_watch_cli(
    *,
    config_path: str | None,
    alerts_path: str | None,
    once: bool,
) -> int:
    """Entry point invoked by ``lighter-mcp watch``."""
    cfg = load_config(config_path)
    apath = Path(alerts_path).expanduser() if alerts_path else DEFAULT_ALERTS_PATH
    alerts = load_alerts(apath)
    return asyncio.run(watch_loop(cfg, alerts, once=once))
