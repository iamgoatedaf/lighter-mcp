"""Shared pytest fixtures.

Tests that need the actual `lighter-agent-kit` checkout consume the
``kit_path`` fixture below. Resolution order:

1. ``$LIGHTER_KIT_PATH`` env var (preferred for CI / contributors).
2. ``~/lighter-agent-kit`` (common dev layout).
3. Tests are skipped if neither resolves to a real directory — they
   never hard-fail because the kit is an external dependency.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _resolve_kit_path() -> Path | None:
    explicit = os.environ.get("LIGHTER_KIT_PATH")
    if explicit:
        return Path(explicit).expanduser()
    fallback = Path.home() / "lighter-agent-kit"
    if fallback.is_dir():
        return fallback
    return None


@pytest.fixture(scope="session")
def kit_path() -> Path:
    p = _resolve_kit_path()
    if p is None or not p.is_dir():
        pytest.skip(
            "lighter-agent-kit not found. Set LIGHTER_KIT_PATH or place the "
            "kit at ~/lighter-agent-kit to run kit-dependent tests."
        )
    return p
