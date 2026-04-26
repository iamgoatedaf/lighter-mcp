"""Config loader for lighter-mcp.

Configuration is TOML-based. The loader supports environment-variable overrides
for a small set of high-impact fields (kit path, mode, host) so that operators
can flip safety knobs without editing files in CI/agent contexts.
"""

from __future__ import annotations

import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

Mode = Literal["readonly", "paper", "live", "funds"]
VALID_MODES: tuple[Mode, ...] = ("readonly", "paper", "live", "funds")

DEFAULT_AUDIT_PATH = "~/.lighter/lighter-mcp/audit.jsonl"
DEFAULT_CONFIRMATION_TTL_S = 120


class ConfigError(ValueError):
    """Raised when the loaded configuration is invalid or inconsistent."""


@dataclass(frozen=True)
class LiveConfig:
    enabled: bool = False
    allowed_symbols: tuple[str, ...] = ()
    max_order_notional_usd: float = 0.0
    max_daily_notional_usd: float = 0.0
    max_leverage: int = 0
    require_confirmation: bool = True


@dataclass(frozen=True)
class FundsConfig:
    transfers_enabled: bool = False
    withdrawals_enabled: bool = False
    max_withdrawal_usd: float = 0.0
    require_confirmation: bool = True


@dataclass(frozen=True)
class Config:
    mode: Mode = "readonly"
    kit_path: Path = field(default_factory=lambda: Path.cwd())
    audit_log: Path = field(default_factory=lambda: Path(DEFAULT_AUDIT_PATH).expanduser())
    confirmation_ttl_s: int = DEFAULT_CONFIRMATION_TTL_S
    host: str = "https://mainnet.zklighter.elliot.ai"
    python_executable: str | None = None  # If None, runner picks kit_path/.venv/bin/python
    live: LiveConfig = field(default_factory=LiveConfig)
    funds: FundsConfig = field(default_factory=FundsConfig)
    source_path: Path | None = None

    def kit_script(self, name: str) -> Path:
        return self.kit_path / "scripts" / name

    def kit_python(self) -> Path:
        if self.python_executable:
            return Path(self.python_executable).expanduser()
        return self.kit_path / ".venv" / "bin" / "python"


def _expand(value: str) -> Path:
    return Path(os.path.expandvars(value)).expanduser()


def _coerce_mode(raw: object, source: str) -> Mode:
    if raw is None:
        return "readonly"
    if not isinstance(raw, str) or raw not in VALID_MODES:
        raise ConfigError(
            f"{source}: mode must be one of {VALID_MODES}, got {raw!r}"
        )
    return raw  # type: ignore[return-value]


def _coerce_symbols(raw: object, source: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(s, str) for s in raw):
        raise ConfigError(f"{source}: allowed_symbols must be a list of strings")
    return tuple(s.upper() for s in raw)


def _coerce_float(raw: object, source: str, default: float = 0.0) -> float:
    if raw is None:
        return default
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ConfigError(f"{source}: expected a number, got {raw!r}")
    return float(raw)


def _coerce_int(raw: object, source: str, default: int = 0) -> int:
    if raw is None:
        return default
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ConfigError(f"{source}: expected an integer, got {raw!r}")
    return raw


def _coerce_bool(raw: object, source: str, default: bool = False) -> bool:
    if raw is None:
        return default
    if not isinstance(raw, bool):
        raise ConfigError(f"{source}: expected a boolean, got {raw!r}")
    return raw


def load_config(path: str | os.PathLike[str] | None = None) -> Config:
    """Load and validate a configuration file.

    Resolution order for the file path:
        1. The argument, if provided.
        2. ``$LIGHTER_MCP_CONFIG`` env var.
        3. ``~/.lighter/lighter-mcp/config.toml``.
        4. Built-in defaults (readonly mode, kit_path=cwd).
    """
    candidate = (
        path
        or os.environ.get("LIGHTER_MCP_CONFIG")
        or "~/.lighter/lighter-mcp/config.toml"
    )
    cfg_path = _expand(str(candidate))
    raw: dict[str, object] = {}
    source_path: Path | None = None
    if cfg_path.is_file():
        # Best-effort permission warning. The config can hold mode flags that
        # are themselves trusted (e.g. live.enabled = true); a world- or
        # group-writable config means anyone on the host could flip them.
        try:
            st = cfg_path.stat()
            if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                print(
                    f"WARNING: lighter-mcp config {cfg_path} is group/world writable; "
                    "tighten permissions with `chmod 600`.",
                    file=sys.stderr,
                    flush=True,
                )
        except OSError:
            pass
        with cfg_path.open("rb") as fh:
            raw = tomllib.load(fh)
        source_path = cfg_path

    mode = _coerce_mode(raw.get("mode"), "config.mode")

    kit_raw = raw.get("kit_path") or os.environ.get("LIGHTER_KIT_PATH")
    if not kit_raw:
        raise ConfigError(
            "kit_path is required: set it in config.toml or via $LIGHTER_KIT_PATH "
            "(absolute path to a lighter-agent-kit checkout)."
        )
    kit_path = _expand(str(kit_raw))
    if not kit_path.is_dir():
        raise ConfigError(f"kit_path does not exist or is not a directory: {kit_path}")

    audit_raw = raw.get("audit_log") or DEFAULT_AUDIT_PATH
    audit_log = _expand(str(audit_raw))

    confirmation_ttl = _coerce_int(
        raw.get("confirmation_ttl_s"),
        "config.confirmation_ttl_s",
        default=DEFAULT_CONFIRMATION_TTL_S,
    )

    host_raw = raw.get("host") or os.environ.get("LIGHTER_HOST") or "https://mainnet.zklighter.elliot.ai"
    if not isinstance(host_raw, str):
        raise ConfigError("config.host must be a string URL")
    parsed_host = urlparse(host_raw)
    if parsed_host.scheme not in ("http", "https") or not parsed_host.netloc:
        raise ConfigError(
            f"config.host must be an http(s) URL with a hostname, got {host_raw!r}"
        )

    python_executable = raw.get("python_executable")
    if python_executable is not None and not isinstance(python_executable, str):
        raise ConfigError("config.python_executable must be a string path")

    live_raw = raw.get("live", {}) or {}
    if not isinstance(live_raw, dict):
        raise ConfigError("config.live must be a table")
    live = LiveConfig(
        enabled=_coerce_bool(live_raw.get("enabled"), "live.enabled"),
        allowed_symbols=_coerce_symbols(live_raw.get("allowed_symbols"), "live.allowed_symbols"),
        max_order_notional_usd=_coerce_float(
            live_raw.get("max_order_notional_usd"), "live.max_order_notional_usd"
        ),
        max_daily_notional_usd=_coerce_float(
            live_raw.get("max_daily_notional_usd"), "live.max_daily_notional_usd"
        ),
        max_leverage=_coerce_int(live_raw.get("max_leverage"), "live.max_leverage"),
        require_confirmation=_coerce_bool(
            live_raw.get("require_confirmation"), "live.require_confirmation", default=True
        ),
    )

    funds_raw = raw.get("funds", {}) or {}
    if not isinstance(funds_raw, dict):
        raise ConfigError("config.funds must be a table")
    funds = FundsConfig(
        transfers_enabled=_coerce_bool(
            funds_raw.get("transfers_enabled"), "funds.transfers_enabled"
        ),
        withdrawals_enabled=_coerce_bool(
            funds_raw.get("withdrawals_enabled"), "funds.withdrawals_enabled"
        ),
        max_withdrawal_usd=_coerce_float(
            funds_raw.get("max_withdrawal_usd"), "funds.max_withdrawal_usd"
        ),
        require_confirmation=_coerce_bool(
            funds_raw.get("require_confirmation"), "funds.require_confirmation", default=True
        ),
    )

    return Config(
        mode=mode,
        kit_path=kit_path,
        audit_log=audit_log,
        confirmation_ttl_s=confirmation_ttl,
        host=host_raw,
        python_executable=python_executable,
        live=live,
        funds=funds,
        source_path=source_path,
    )
