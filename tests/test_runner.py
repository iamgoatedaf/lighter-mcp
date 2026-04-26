"""Tests for the kit subprocess runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lighter_mcp.config import Config, FundsConfig, LiveConfig
from lighter_mcp.runner import KitRunner, RunnerError


def _config(kit_path: Path, tmp_path: Path) -> Config:
    return Config(
        mode="readonly",
        kit_path=kit_path,
        audit_log=tmp_path / "audit.jsonl",
        live=LiveConfig(),
        funds=FundsConfig(),
    )


@pytest.mark.asyncio
async def test_runner_invokes_query_system_status_against_live_api(
    kit_path: Path, tmp_path: Path
) -> None:
    """Hits Lighter mainnet for system status. Skip if offline."""
    runner = KitRunner(_config(kit_path, tmp_path))
    try:
        result = await runner.run("query.py", ["system", "status"], timeout_s=20.0)
    except RunnerError as exc:
        pytest.skip(f"live API unreachable: {exc}")
    assert isinstance(result.data, dict)
    assert result.data.get("status") == 200


@pytest.mark.asyncio
async def test_runner_translates_kit_errors(kit_path: Path, tmp_path: Path) -> None:
    """An unknown subcommand should produce a RunnerError with the kit's message."""
    runner = KitRunner(_config(kit_path, tmp_path))
    with pytest.raises(RunnerError) as excinfo:
        await runner.run("query.py", ["definitely-not-a-command"])
    err = excinfo.value
    assert err.exit_code is not None
    payload = json.dumps(err.to_payload())
    assert "argv" in payload
