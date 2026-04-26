"""Tests for the audit log redaction and append behavior."""

from __future__ import annotations

import json
from pathlib import Path

from lighter_mcp.audit import AuditLog


def test_audit_redacts_secrets_in_args(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append(
        tool="lighter_live_limit_order",
        mode="live",
        args={
            "symbol": "BTC",
            "api_private_key": "supersecret",
            "tx_info": {"sig": "0xdeadbeef"},
        },
        result={"ok": True},
    )
    line = (tmp_path / "audit.jsonl").read_text().strip()
    record = json.loads(line)
    assert record["args"]["symbol"] == "BTC"
    assert record["args"]["api_private_key"] == "[REDACTED]"
    assert record["args"]["tx_info"] == "[REDACTED]"


def test_audit_truncates_long_strings(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "audit.jsonl")
    long_value = "x" * 10_000
    log.append(
        tool="t",
        mode="readonly",
        args={"blob": long_value},
        result=None,
    )
    record = json.loads((tmp_path / "audit.jsonl").read_text().strip())
    assert record["args"]["blob"].endswith("[truncated]")
    assert len(record["args"]["blob"]) <= 4096 + len("…[truncated]")


def test_audit_appends_multiple_records(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "audit.jsonl")
    for i in range(3):
        log.append(tool=f"t{i}", mode="paper", args={"i": i}, result={"i": i})
    lines = (tmp_path / "audit.jsonl").read_text().splitlines()
    assert len(lines) == 3
    assert [json.loads(line)["tool"] for line in lines] == ["t0", "t1", "t2"]
