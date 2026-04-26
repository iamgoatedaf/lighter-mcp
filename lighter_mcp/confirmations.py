"""Two-step confirmation tokens for high-risk MCP tool calls.

Pattern:
    1. First call with no ``confirmation_id`` returns a structured preview
       and an issued token bound to (tool, canonical_args_hash).
    2. Second call must repeat the *same* args plus the issued token. If the
       token matches the bound digest and is unexpired, the call proceeds.

This keeps two-step interactions inside one tool from the agent's perspective
(no separate ``preview_*`` / ``execute_*`` tools), and prevents replay or
bait-and-switch where a confirmation is reused with different args.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any


class ConfirmationError(RuntimeError):
    """Confirmation token is missing, unknown, expired, or mismatched."""


@dataclass(frozen=True)
class _Pending:
    tool: str
    digest: str
    expires_at: float


def _digest(tool: str, args: dict[str, Any]) -> str:
    payload = json.dumps({"tool": tool, "args": args}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class ConfirmationStore:
    """In-memory pending confirmations. Single-process; not durable across restarts."""

    def __init__(self, ttl_s: int) -> None:
        if ttl_s <= 0:
            raise ValueError(
                f"confirmation TTL must be > 0 seconds (got {ttl_s})"
            )
        self._ttl = ttl_s
        self._pending: dict[str, _Pending] = {}

    def issue(self, *, tool: str, args: dict[str, Any]) -> tuple[str, float]:
        # GC before issuing a new token so we never leak unbounded state, but
        # avoid touching the freshly-stored entry afterward.
        self._gc()
        token = secrets.token_urlsafe(16)
        expires_at = time.time() + self._ttl
        self._pending[token] = _Pending(
            tool=tool, digest=_digest(tool, args), expires_at=expires_at
        )
        return token, expires_at

    def consume(
        self, *, tool: str, args: dict[str, Any], token: str
    ) -> None:
        # Peek-then-pop: validate tool/digest/expiry FIRST. Only then remove
        # the entry. Prior versions popped on lookup which let a malformed
        # second call (wrong tool, wrong args) burn a valid token and grief
        # the user into having to re-preview. The token is still single-use:
        # we delete it on successful validation below.
        pending = self._pending.get(token)
        if pending is None:
            self._gc()
            raise ConfirmationError(
                "unknown or already-used confirmation_id; call again without one to re-preview."
            )
        if pending.expires_at < time.time():
            self._pending.pop(token, None)
            raise ConfirmationError(
                "confirmation_id has expired; call again without one to re-preview."
            )
        if pending.tool != tool:
            raise ConfirmationError(
                f"confirmation_id was issued for a different tool ({pending.tool})."
            )
        if pending.digest != _digest(tool, args):
            raise ConfirmationError(
                "arguments differ from the previewed call; re-preview before executing."
            )
        self._pending.pop(token, None)

    def _gc(self) -> None:
        now = time.time()
        for tok, p in list(self._pending.items()):
            if p.expires_at < now:
                self._pending.pop(tok, None)
