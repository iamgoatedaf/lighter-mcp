"""Subprocess runner for lighter-agent-kit scripts.

The runner shells out to the kit's ``scripts/{query,paper,trade}.py`` entrypoints
using the kit's own pinned virtual environment. It captures stdout, parses the
JSON response, and normalizes failures into a single ``RunnerError`` shape so
callers can rely on the result type.

Why subprocess over importing the SDK directly:
    - The kit ships pinned, vendored dependencies and signer logic that have
      been audited end-to-end by elliottech. Reusing that path avoids redoing
      tx-signing work and keeps wire formats identical.
    - Errors and JSON shapes from the kit are already documented in
      ``references/schemas-*.md`` of the kit; we inherit that contract.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .config import Config


class RunnerError(RuntimeError):
    """Wraps a non-zero exit, stderr, or invalid JSON output from a kit script."""

    def __init__(
        self,
        message: str,
        *,
        script: str,
        argv: list[str],
        exit_code: int | None = None,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.script = script
        self.argv = argv
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr

    def to_payload(self) -> dict:
        """Render as a JSON-serializable payload for the audit log / tool error envelope."""
        return {
            "error": str(self),
            "script": self.script,
            "argv": self.argv,
            "exit_code": self.exit_code,
            "stderr": (self.stderr or "")[-2000:],
        }


@dataclass(frozen=True)
class RunResult:
    """Successful run of a kit script."""

    data: dict | list
    raw_stdout: str
    argv: list[str]


class KitRunner:
    """Run kit scripts as subprocesses and parse JSON responses."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._python = config.kit_python()

    @property
    def python(self) -> Path:
        return self._python

    def _build_argv(self, script: str, args: list[str]) -> list[str]:
        script_path = self._config.kit_script(script)
        return [str(self._python), str(script_path), *args]

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.setdefault("LIGHTER_HOST", self._config.host)
        env.setdefault("PYTHONUNBUFFERED", "1")
        return env

    async def run(
        self,
        script: str,
        args: list[str],
        *,
        timeout_s: float = 60.0,
    ) -> RunResult:
        """Run ``script`` with ``args`` and return parsed JSON output.

        Raises ``RunnerError`` on non-zero exit, missing JSON, or timeout.
        """
        argv = self._build_argv(script, args)

        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._build_env(),
                cwd=str(self._config.kit_path),
            )
        except FileNotFoundError as exc:
            raise RunnerError(
                f"kit python or script not found: {exc}",
                script=script,
                argv=argv,
            ) from exc

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_s
            )
        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.wait()
            raise RunnerError(
                f"kit script {script} timed out after {timeout_s}s",
                script=script,
                argv=argv,
                exit_code=None,
            ) from exc

        stdout = stdout_bytes.decode(errors="replace")
        stderr = stderr_bytes.decode(errors="replace")

        if proc.returncode != 0:
            data = _try_parse_json(stdout)
            err_msg = (
                data.get("error") if isinstance(data, dict) and "error" in data else None
            )
            raise RunnerError(
                err_msg or f"kit script {script} exited with code {proc.returncode}",
                script=script,
                argv=argv,
                exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
            )

        data = _try_parse_json(stdout)
        if data is None:
            raise RunnerError(
                f"kit script {script} returned non-JSON output",
                script=script,
                argv=argv,
                exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
            )

        # The kit also signals errors via {"error": ...} with exit code 0 in some
        # diagnostics paths; normalize that into RunnerError too.
        if isinstance(data, dict) and "error" in data and len(data) == 1:
            raise RunnerError(
                str(data["error"]),
                script=script,
                argv=argv,
                exit_code=0,
                stdout=stdout,
                stderr=stderr,
            )

        return RunResult(data=data, raw_stdout=stdout, argv=argv)


def _try_parse_json(text: str) -> dict | list | None:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
