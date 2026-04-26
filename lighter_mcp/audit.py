"""Append-only JSONL audit log.

Records every tool invocation with timestamp, mode, sanitized arguments and
result, and any associated confirmation id. The log is append-only, written
under ``audit_log`` in the config (default ``~/.lighter/lighter-mcp/audit.jsonl``).

Sanitization rules (best effort; assume nothing is safe by default):
    - Drops any key whose name matches a credential-like substring.
    - Truncates large stdout/stderr blobs.
    - Never logs the kit's signed tx_info bytes.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from threading import Lock
from typing import Any

try:
    import fcntl  # POSIX advisory file locking
    _HAVE_FCNTL = True
except ImportError:  # pragma: no cover — Windows
    _HAVE_FCNTL = False

_REDACTED = "[REDACTED]"
_SECRET_SUBSTRINGS = (
    "private_key",
    "privatekey",
    "secret",
    "api_key",
    "apikey",
    "auth",
    "token",
    "signature",
    "sig",
    "tx_info",
    "credential",
    "passphrase",
    "password",
)
_MAX_STR_LEN = 4096


class AuditLog:
    """Thread-unsafe but asyncio-safe append-only JSONL writer."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Intra-process lock: serializes writes from concurrent asyncio tasks.
        # Combined with O_APPEND + flock() this also keeps records intact when
        # multiple lighter-mcp processes share the same audit file.
        self._lock = Lock()

    @property
    def path(self) -> Path:
        return self._path

    def append(
        self,
        *,
        tool: str,
        mode: str,
        args: dict[str, Any] | None,
        result: dict[str, Any] | list[Any] | None,
        confirmation_id: str | None = None,
        ok: bool = True,
        error: str | None = None,
    ) -> None:
        record = {
            "ts": time.time(),
            "tool": tool,
            "mode": mode,
            "ok": ok,
            "args": _sanitize(args),
            "result": _sanitize(result, depth=2),
            "confirmation_id": confirmation_id,
            "error": error,
        }
        line = json.dumps(record, default=_json_fallback, ensure_ascii=False) + "\n"
        try:
            with self._lock, self._path.open("a", encoding="utf-8") as fh:
                if _HAVE_FCNTL:
                    try:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                    except OSError:
                        pass
                fh.write(line)
                fh.flush()
        except OSError as exc:
            # The audit log must never silently break the request. We surface
            # the failure to stderr so an operator notices, but we do NOT
            # raise — the agent's pipeline keeps working. Operators get the
            # same warning every call until disk/permissions are repaired.
            print(
                f"WARNING: lighter-mcp audit write failed ({self._path}): {exc}",
                file=sys.stderr,
                flush=True,
            )


def _sanitize(value: Any, depth: int = 4) -> Any:
    if depth <= 0:
        return _REDACTED
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) > _MAX_STR_LEN:
            return value[:_MAX_STR_LEN] + "…[truncated]"
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if any(s in key.lower() for s in _SECRET_SUBSTRINGS):
                out[key] = _REDACTED
            else:
                out[key] = _sanitize(v, depth - 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_sanitize(v, depth - 1) for v in value]
    return _sanitize(repr(value), depth - 1)


def _json_fallback(obj: Any) -> str:
    return repr(obj)
