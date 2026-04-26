"""Tests for the two-step confirmation store."""

from __future__ import annotations

import time

import pytest

from lighter_mcp.confirmations import ConfirmationError, ConfirmationStore


def test_issue_and_consume_roundtrip() -> None:
    store = ConfirmationStore(ttl_s=60)
    args = {"symbol": "BTC", "amount": 1.0}
    token, expires_at = store.issue(tool="lighter_live_market_order", args=args)
    assert isinstance(token, str) and len(token) > 8
    assert expires_at > time.time()
    store.consume(tool="lighter_live_market_order", args=args, token=token)


def test_token_is_single_use() -> None:
    store = ConfirmationStore(ttl_s=60)
    token, _ = store.issue(tool="t", args={"x": 1})
    store.consume(tool="t", args={"x": 1}, token=token)
    with pytest.raises(ConfirmationError, match="unknown"):
        store.consume(tool="t", args={"x": 1}, token=token)


def test_args_must_match() -> None:
    store = ConfirmationStore(ttl_s=60)
    token, _ = store.issue(tool="t", args={"symbol": "BTC", "amount": 1.0})
    with pytest.raises(ConfirmationError, match="differ"):
        store.consume(tool="t", args={"symbol": "BTC", "amount": 2.0}, token=token)


def test_tool_name_must_match() -> None:
    store = ConfirmationStore(ttl_s=60)
    token, _ = store.issue(tool="lighter_live_market_order", args={"x": 1})
    with pytest.raises(ConfirmationError, match="different tool"):
        store.consume(tool="lighter_funds_withdraw", args={"x": 1}, token=token)


def test_failed_validation_does_not_burn_token() -> None:
    """A wrong-tool/wrong-args attempt must NOT consume the token (peek-then-pop).

    Otherwise a buggy or hostile second call could grief-DoS the user, forcing
    them to re-preview every action.
    """
    store = ConfirmationStore(ttl_s=60)
    token, _ = store.issue(tool="t", args={"x": 1})
    with pytest.raises(ConfirmationError, match="different tool"):
        store.consume(tool="other", args={"x": 1}, token=token)
    with pytest.raises(ConfirmationError, match="differ"):
        store.consume(tool="t", args={"x": 2}, token=token)
    # Original (correct) call still works.
    store.consume(tool="t", args={"x": 1}, token=token)
    # And it's now single-use.
    with pytest.raises(ConfirmationError, match="unknown"):
        store.consume(tool="t", args={"x": 1}, token=token)


def test_expired_token() -> None:
    store = ConfirmationStore(ttl_s=1)
    token, _ = store.issue(tool="t", args={"x": 1})
    # Force expiry by rewriting the entry's expires_at into the past.
    pending = store._pending[token]
    store._pending[token] = pending.__class__(
        tool=pending.tool, digest=pending.digest, expires_at=time.time() - 1
    )
    with pytest.raises(ConfirmationError, match="expired"):
        store.consume(tool="t", args={"x": 1}, token=token)


def test_ttl_must_be_positive() -> None:
    with pytest.raises(ValueError, match="must be > 0"):
        ConfirmationStore(ttl_s=0)
    with pytest.raises(ValueError, match="must be > 0"):
        ConfirmationStore(ttl_s=-5)
