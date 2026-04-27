"""One-shot installer: ``lighter-mcp init``.

The job here is to take a freshly ``pipx install``-ed (or ``uvx``-ran) package
and bring it to the state that previously required half a dozen shell commands:

    * a ``lighter-agent-kit`` checkout in a known location,
    * a default ``~/.lighter/lighter-mcp/config.toml`` pointing at it,
    * the local agent's MCP config (Cursor / Claude / Codex / Claude Desktop)
      patched to launch ``lighter-mcp stdio`` automatically,
    * the agent's slash-command / sub-agent / hook scaffolds dropped in place.

Design choices worth knowing about:

    * **No second venv for the kit.** The kit's ``scripts/_sdk.py`` self-vendors
      its requirements into ``<kit>/.vendor/pyX.Y/`` on first use, so we can
      reuse the same Python interpreter that runs ``lighter-mcp`` itself. The
      installer writes that interpreter path into ``python_executable`` of the
      generated config so the runner doesn't fall back to a non-existent
      ``<kit>/.venv/bin/python``.

    * **Idempotent.** Re-running ``lighter-mcp init`` is a no-op when nothing
      changed; if a config already exists we don't clobber it. ``--force`` is
      the escape hatch.

    * **Fail soft on adapter patches.** Failing to patch one agent's config
      should not abort the whole install — the user might be on a machine that
      has Claude Desktop but not Cursor.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

# The kit upstream. Auto-install pulls a tarball from this repository.
_KIT_REPO = "https://github.com/elliottech/lighter-agent-kit"
_KIT_TARBALL = f"{_KIT_REPO}/archive/refs/heads/main.tar.gz"

# Where on disk we put things by default.
_DEFAULT_INSTALL_ROOT = Path("~/.lighter/lighter-mcp").expanduser()
_DEFAULT_KIT_PATH = Path("~/.lighter/lighter-agent-kit").expanduser()

# Adapter ids we recognize. Keep in sync with ``Agent.NAMES`` below and with
# the ``adapters/`` folder layout shipped in the wheel.
_KNOWN_AGENTS = ("cursor", "claude-code", "claude-desktop", "codex")


class InstallError(RuntimeError):
    """Raised when the installer cannot proceed and the caller must intervene."""


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stderr.isatty()


def _c(code: str, text: str) -> str:
    if not _supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def _step(msg: str) -> None:
    print(f"{_c('36', '→')} {msg}", file=sys.stderr, flush=True)


def _ok(msg: str) -> None:
    print(f"{_c('32', '✓')} {msg}", file=sys.stderr, flush=True)


def _warn(msg: str) -> None:
    print(f"{_c('33', '!')} {msg}", file=sys.stderr, flush=True)


def _fail(msg: str) -> None:
    print(f"{_c('31', '✗')} {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Agent detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Agent:
    """A locally installed MCP-capable agent the installer can wire into."""

    name: str
    config_path: Path
    scope: str  # "user" or "project"

    @property
    def display(self) -> str:
        return {
            "cursor": "Cursor",
            "claude-code": "Claude Code",
            "claude-desktop": "Claude Desktop",
            "codex": "Codex",
        }.get(self.name, self.name)


def _claude_desktop_config_path() -> Path:
    """Return the platform-specific Claude Desktop config path."""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA") or str(home / "AppData" / "Roaming")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    # Linux: Claude Desktop is unofficial, but follow the same XDG-ish layout.
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(home / ".config")
    return Path(xdg) / "Claude" / "claude_desktop_config.json"


def detect_agents(*, project_dir: Path | None = None) -> list[Agent]:
    """Return the list of locally configurable agents.

    A configurable agent is one whose MCP config either exists already or whose
    parent directory is writable so we can create it. The returned list is
    intentionally generous: presence of a ``~/.cursor`` directory is enough to
    add Cursor — we'd rather offer too many than too few during ``init``.
    """
    home = Path.home()
    found: list[Agent] = []

    # Cursor: per-user lives at ~/.cursor/mcp.json; per-project at
    # <project>/.cursor/mcp.json. We register both when applicable.
    cursor_user = home / ".cursor" / "mcp.json"
    if cursor_user.parent.exists() or cursor_user.exists():
        found.append(Agent("cursor", cursor_user, "user"))
    if project_dir is not None:
        cursor_project = project_dir / ".cursor" / "mcp.json"
        # Project-scoped Cursor is opt-in: only register if the project clearly
        # uses Cursor (folder exists) so we don't litter random checkouts.
        if cursor_project.parent.exists():
            found.append(Agent("cursor", cursor_project, "project"))

    # Claude Code: ~/.claude/mcp.json
    claude_code = home / ".claude" / "mcp.json"
    if claude_code.parent.exists() or claude_code.exists():
        found.append(Agent("claude-code", claude_code, "user"))

    # Claude Desktop: platform-specific.
    claude_desktop = _claude_desktop_config_path()
    if claude_desktop.exists() or claude_desktop.parent.exists():
        found.append(Agent("claude-desktop", claude_desktop, "user"))

    # Codex: each plugin lives under ~/.codex/plugins/<name>/ — we always
    # offer to install when ~/.codex exists, regardless of whether the
    # specific plugin already does.
    codex_root = home / ".codex"
    if codex_root.exists():
        found.append(Agent("codex", codex_root / "plugins" / "lighter", "user"))

    return found


# ---------------------------------------------------------------------------
# Kit auto-install
# ---------------------------------------------------------------------------


def _has_git() -> bool:
    return shutil.which("git") is not None


def _git_clone(url: str, dest: Path) -> None:
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch", url, str(dest)],
        check=True,
    )


def _download_tarball(url: str, dest: Path) -> None:
    """Download a .tar.gz and extract it into ``dest``.

    The archive's top-level directory is stripped so the layout under ``dest``
    matches a normal git checkout.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lighter-kit-") as tmp_str:
        tmp = Path(tmp_str)
        archive = tmp / "kit.tar.gz"
        with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 (HTTPS pinned)
            archive.write_bytes(resp.read())
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            if not members:
                raise InstallError("kit tarball is empty")
            top = members[0].name.split("/", 1)[0]
            tar.extractall(tmp, filter="data")  # type: ignore[arg-type]
        extracted = tmp / top
        if not extracted.is_dir():
            raise InstallError(f"unexpected tarball layout: {top}")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(extracted), str(dest))


def install_kit(target: Path = _DEFAULT_KIT_PATH, *, force: bool = False) -> Path:
    """Ensure a usable ``lighter-agent-kit`` checkout exists at ``target``.

    Strategy:

    1. If ``target`` already looks like a kit checkout (has ``scripts/query.py``),
       return it untouched unless ``force=True``.
    2. Else use ``git clone`` if ``git`` is on PATH (faster, gives a proper repo
       the user can ``git pull``).
    3. Else fall back to downloading the latest source tarball over HTTPS — no
       extra binaries required on the host.

    The kit self-vendors its Python deps the first time one of its scripts is
    invoked, so we do **not** create a virtualenv here.
    """
    target = target.expanduser()
    looks_installed = (target / "scripts" / "query.py").is_file()
    if looks_installed and not force:
        _ok(f"kit already present: {target}")
        return target

    if force and target.exists():
        _step(f"removing existing kit at {target} (--force)")
        shutil.rmtree(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    if _has_git():
        _step(f"cloning kit into {target}")
        try:
            _git_clone(_KIT_REPO, target)
        except subprocess.CalledProcessError as exc:
            raise InstallError(f"git clone failed: {exc}") from exc
    else:
        _step(f"downloading kit tarball into {target} (git not found)")
        try:
            _download_tarball(_KIT_TARBALL, target)
        except Exception as exc:
            raise InstallError(f"kit download failed: {exc}") from exc

    if not (target / "scripts" / "query.py").is_file():
        raise InstallError(
            f"kit install at {target} is missing scripts/query.py — aborting"
        )
    _ok(f"kit installed at {target}")
    return target


# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------


_CONFIG_TEMPLATE = """\
# Generated by `lighter-mcp init` on {when}.
# Run `lighter-mcp doctor` after edits to validate.

mode = "{mode}"
kit_path = {kit_path!r}
python_executable = {python!r}
audit_log = "~/.lighter/lighter-mcp/audit.jsonl"
host = "{host}"

# Live trading is OFF until you flip these on. See docs/configuration.md
# and DISCLAIMER.md before enabling.
[live]
enabled = false
allowed_symbols = []
max_order_notional_usd = 0
max_daily_notional_usd = 0
max_leverage = 0
require_confirmation = true

[funds]
transfers_enabled = false
withdrawals_enabled = false
max_withdrawal_usd = 0
require_confirmation = true
"""


def write_default_config(
    *,
    target: Path,
    kit_path: Path,
    python_executable: Path,
    mode: str = "readonly",
    host: str = "https://mainnet.zklighter.elliot.ai",
    force: bool = False,
) -> Path:
    """Write a default lighter-mcp config TOML if none exists."""
    target = target.expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        _ok(f"config already present: {target} (use --force to overwrite)")
        return target

    from datetime import datetime, timezone

    body = _CONFIG_TEMPLATE.format(
        when=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        mode=mode,
        kit_path=str(kit_path),
        python=str(python_executable),
        host=host,
    )
    target.write_text(body)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    _ok(f"config written: {target}")
    return target


# ---------------------------------------------------------------------------
# Agent config patching
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        # Don't blow away unparseable user config; quarantine it instead.
        backup = path.with_suffix(path.suffix + ".bak")
        path.replace(backup)
        _warn(f"existing {path} was not valid JSON — backed up to {backup}")
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _server_block(*, command: str, lighter_config: Path) -> dict:
    return {
        "command": command,
        "args": ["stdio"],
        "env": {"LIGHTER_MCP_CONFIG": str(lighter_config)},
    }


def patch_mcp_json(
    config_path: Path,
    *,
    command: str,
    lighter_config: Path,
    server_name: str = "lighter",
) -> None:
    """Insert (or update) a ``lighter`` entry in an MCP-style JSON config.

    Supports the two prevailing shapes:

        {"mcpServers": {"lighter": {...}}}      # Cursor, Claude, Claude Desktop
        {"mcp": {"servers": {"lighter": {...}}}}  # alternate shape some agents use

    We default to ``mcpServers`` and never delete unrelated keys.
    """
    data = _read_json(config_path)
    block = _server_block(command=command, lighter_config=lighter_config)
    if isinstance(data.get("mcp"), dict) and isinstance(
        data["mcp"].get("servers"), dict
    ):
        data["mcp"]["servers"][server_name] = block
    else:
        servers = data.setdefault("mcpServers", {})
        if not isinstance(servers, dict):
            raise InstallError(
                f"{config_path}: 'mcpServers' is not an object — refusing to overwrite"
            )
        servers[server_name] = block
    _write_json(config_path, data)
    _ok(f"patched {config_path}")


# ---------------------------------------------------------------------------
# Adapter scaffolds (slash-commands, sub-agent, hook)
# ---------------------------------------------------------------------------


def _adapters_root() -> Path:
    """Find the bundled ``adapters/`` directory, whether installed or in source.

    When installed via wheel the directory ships under
    ``lighter_mcp/_data/adapters``. In a development checkout it lives at
    ``<repo>/adapters``.
    """
    candidates = [
        Path(__file__).parent / "_data" / "adapters",
        Path(__file__).parent.parent / "adapters",
    ]
    for cand in candidates:
        if cand.is_dir():
            return cand
    raise InstallError(
        "adapters/ directory not found in either the installed package data "
        "or the source tree — package build is broken"
    )


def _configs_root() -> Path:
    candidates = [
        Path(__file__).parent / "_data" / "configs",
        Path(__file__).parent.parent / "configs",
    ]
    for cand in candidates:
        if cand.is_dir():
            return cand
    return Path(__file__).parent  # absolute last resort, never useful


def _copytree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        target = dst / entry.name
        if entry.is_dir():
            _copytree(entry, target)
        else:
            shutil.copy2(entry, target)


def install_cursor_scaffolds(target: Path) -> None:
    """Drop Cursor rules / commands / sub-agent / hook into ``<target>/.cursor``.

    ``target`` is usually the project root (``--scope project``) or the user
    home (``--scope user``).
    """
    adapters = _adapters_root()
    cursor_dir = target / ".cursor"
    cursor_dir.mkdir(parents=True, exist_ok=True)
    (cursor_dir / "rules").mkdir(exist_ok=True)
    (cursor_dir / "commands").mkdir(exist_ok=True)
    (cursor_dir / "agents").mkdir(exist_ok=True)

    # Rule and hook are Cursor-specific.
    cursor_src = adapters / "cursor"
    if (cursor_src / "rules" / "lighter-safety.mdc").is_file():
        shutil.copy2(
            cursor_src / "rules" / "lighter-safety.mdc",
            cursor_dir / "rules" / "lighter-safety.mdc",
        )
    if (cursor_src / "hooks.json").is_file():
        shutil.copy2(cursor_src / "hooks.json", cursor_dir / "hooks.json")

    # Slash-commands and sub-agent come from the shared source-of-truth.
    shared = adapters / "_shared"
    for md in (shared / "commands").glob("*.md"):
        shutil.copy2(md, cursor_dir / "commands" / md.name)
    for md in (shared / "agents").glob("*.md"):
        shutil.copy2(md, cursor_dir / "agents" / md.name)
    _ok(f"installed Cursor scaffolds into {cursor_dir}")


def install_claude_code_scaffolds(target: Path) -> None:
    adapters = _adapters_root()
    claude_dir = target / ".claude"
    (claude_dir / "commands").mkdir(parents=True, exist_ok=True)
    (claude_dir / "agents").mkdir(parents=True, exist_ok=True)
    (claude_dir / "hooks").mkdir(parents=True, exist_ok=True)

    shared = adapters / "_shared"
    for md in (shared / "commands").glob("*.md"):
        shutil.copy2(md, claude_dir / "commands" / md.name)
    for md in (shared / "agents").glob("*.md"):
        shutil.copy2(md, claude_dir / "agents" / md.name)
    hook = shared / "hooks" / "after-lighter-trade.sh"
    if hook.is_file():
        dest = claude_dir / "hooks" / "post-tool-call.sh"
        shutil.copy2(hook, dest)
        try:
            dest.chmod(0o755)
        except OSError:
            pass
    _ok(f"installed Claude Code scaffolds into {claude_dir}")


def install_codex_plugin(target: Path) -> None:
    """Lay out a Codex plugin at ``<target>`` (defaults to ~/.codex/plugins/lighter)."""
    adapters = _adapters_root()
    target.mkdir(parents=True, exist_ok=True)
    src = adapters / "codex" / ".codex-plugin"
    if src.is_dir():
        _copytree(src, target)
    skills = adapters / "codex" / "skills"
    if skills.is_dir():
        _copytree(skills, target / "skills")
    _ok(f"installed Codex plugin into {target}")


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


@dataclass
class InitResult:
    config_path: Path
    kit_path: Path
    patched_agents: list[str] = field(default_factory=list)
    skipped_agents: list[str] = field(default_factory=list)


def run_init(
    *,
    install_root: Path = _DEFAULT_INSTALL_ROOT,
    kit_path: Path | None = None,
    mode: str = "readonly",
    agents: Sequence[str] | None = None,
    project_dir: Path | None = None,
    force: bool = False,
    auto_install_kit: bool = True,
    skip_scaffolds: bool = False,
) -> InitResult:
    """End-to-end first-time setup. Returns details for the caller to print."""
    install_root = install_root.expanduser()
    install_root.mkdir(parents=True, exist_ok=True)

    if kit_path is None:
        kit_path = _DEFAULT_KIT_PATH
    kit_path = kit_path.expanduser()

    if auto_install_kit:
        install_kit(kit_path, force=force)
    elif not (kit_path / "scripts" / "query.py").is_file():
        raise InstallError(
            f"--no-install-kit was passed but {kit_path}/scripts/query.py is missing"
        )

    config_path = install_root / "config.toml"
    write_default_config(
        target=config_path,
        kit_path=kit_path,
        python_executable=Path(sys.executable),
        mode=mode,
        force=force,
    )

    detected = detect_agents(project_dir=project_dir)
    selected = _select_agents(detected, agents)
    patched: list[str] = []
    skipped: list[str] = []

    server_command = _resolve_server_command()

    for agent in selected:
        try:
            _wire_agent(
                agent,
                server_command=server_command,
                lighter_config=config_path,
                project_dir=project_dir,
                skip_scaffolds=skip_scaffolds,
            )
            patched.append(f"{agent.name}:{agent.scope}")
        except InstallError as exc:
            _warn(f"{agent.display}: {exc}")
            skipped.append(f"{agent.name}:{agent.scope}")

    if not patched:
        _warn(
            "no agents were patched. You can wire one manually using the "
            "snippet printed by `lighter-mcp init --print-snippet`."
        )

    return InitResult(
        config_path=config_path,
        kit_path=kit_path,
        patched_agents=patched,
        skipped_agents=skipped,
    )


def _select_agents(
    detected: Iterable[Agent], requested: Sequence[str] | None
) -> list[Agent]:
    detected = list(detected)
    if requested is None:
        return detected
    requested_set = {r.lower() for r in requested}
    unknown = requested_set - set(_KNOWN_AGENTS)
    if unknown:
        raise InstallError(
            f"unknown agent(s): {sorted(unknown)} "
            f"(expected: {list(_KNOWN_AGENTS)})"
        )
    return [a for a in detected if a.name in requested_set]


def _resolve_server_command() -> str:
    """Find the ``lighter-mcp`` executable to put in agent configs.

    Prefer a stable, on-PATH command (so agent configs stay portable across
    pipx upgrades). Fall back to the absolute path of the currently running
    interpreter's console-script when ``lighter-mcp`` isn't on PATH yet
    (e.g. ``uvx`` ephemeral envs).
    """
    on_path = shutil.which("lighter-mcp")
    if on_path:
        return on_path

    # Same directory as the current python; this is the case for venvs and
    # pipx-managed environments before they're added to PATH.
    candidate = Path(sys.executable).parent / "lighter-mcp"
    if candidate.is_file():
        return str(candidate)

    # Last resort: launch via the module entrypoint.
    return f"{sys.executable} -m lighter_mcp.server"


def _wire_agent(
    agent: Agent,
    *,
    server_command: str,
    lighter_config: Path,
    project_dir: Path | None,
    skip_scaffolds: bool,
) -> None:
    if agent.name == "cursor":
        patch_mcp_json(
            agent.config_path,
            command=server_command,
            lighter_config=lighter_config,
        )
        if not skip_scaffolds:
            target = (
                project_dir
                if agent.scope == "project" and project_dir is not None
                else Path.home()
            )
            install_cursor_scaffolds(target)
        return

    if agent.name == "claude-code":
        patch_mcp_json(
            agent.config_path,
            command=server_command,
            lighter_config=lighter_config,
        )
        if not skip_scaffolds:
            install_claude_code_scaffolds(Path.home())
        return

    if agent.name == "claude-desktop":
        patch_mcp_json(
            agent.config_path,
            command=server_command,
            lighter_config=lighter_config,
        )
        # Claude Desktop has no slash-command UI surface; nothing to scaffold.
        return

    if agent.name == "codex":
        if not skip_scaffolds:
            install_codex_plugin(agent.config_path)
        return

    raise InstallError(f"unknown agent: {agent.name}")


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------


def render_summary(result: InitResult) -> str:
    lines = [
        "",
        _c("1;32", "✓ lighter-mcp ready."),
        "",
        f"  Config:    {result.config_path}",
        f"  Kit:       {result.kit_path}",
    ]
    if result.patched_agents:
        lines.append(f"  Wired:     {', '.join(result.patched_agents)}")
    if result.skipped_agents:
        lines.append(f"  Skipped:   {', '.join(result.skipped_agents)}")
    lines += [
        "",
        "Next steps:",
        "  1. Restart your agent (Cursor / Claude / Codex) to pick up MCP changes.",
        "  2. Try in your agent: `/lighter-status` or ask 'show top funding rates'.",
        "  3. To enable paper or live trading, edit the config above and re-run",
        "     `lighter-mcp doctor`. Live trading also requires reading DISCLAIMER.md.",
        "",
    ]
    return "\n".join(lines)


def run_init_cli(args) -> int:
    """Wired into ``lighter-mcp init`` in ``server.py``."""
    project_dir = Path(args.project_dir).expanduser() if args.project_dir else Path.cwd()
    requested = args.agents.split(",") if args.agents else None

    try:
        result = run_init(
            install_root=Path(args.install_root).expanduser(),
            kit_path=Path(args.kit_path).expanduser() if args.kit_path else None,
            mode=args.mode,
            agents=requested,
            project_dir=project_dir,
            force=args.force,
            auto_install_kit=not args.no_install_kit,
            skip_scaffolds=args.no_scaffolds,
        )
    except InstallError as exc:
        _fail(str(exc))
        return 2

    print(render_summary(result))

    if not args.no_doctor:
        _step("running doctor smoke check…")
        env = os.environ.copy()
        env["LIGHTER_MCP_CONFIG"] = str(result.config_path)
        proc = subprocess.run(  # noqa: S603 — args are trusted
            [sys.executable, "-m", "lighter_mcp.server", "doctor"],
            env=env,
        )
        if proc.returncode != 0:
            _warn(
                "doctor reported a problem above. The kit may need its first "
                "self-vendor pass — try running it once more, or `lighter-mcp "
                "doctor` directly."
            )
            return 0  # Non-fatal: install succeeded, just couldn't smoke-test.

    return 0


def add_init_args(parser) -> None:
    """Register the ``init`` subcommand's flags. Called from ``server.py``."""
    parser.add_argument(
        "--mode",
        default="readonly",
        choices=("readonly", "paper", "live", "funds"),
        help="Initial mode for the generated config (default: readonly).",
    )
    parser.add_argument(
        "--kit-path",
        help="Where to install (or find) lighter-agent-kit. "
        f"Default: {_DEFAULT_KIT_PATH}",
    )
    parser.add_argument(
        "--install-root",
        default=str(_DEFAULT_INSTALL_ROOT),
        help=f"Where to write config + audit log. Default: {_DEFAULT_INSTALL_ROOT}",
    )
    parser.add_argument(
        "--agents",
        help=(
            "Comma-separated subset of agents to wire (default: all detected). "
            f"Choose from: {','.join(_KNOWN_AGENTS)}."
        ),
    )
    parser.add_argument(
        "--project-dir",
        help="Project root for project-scoped Cursor adapter (default: cwd).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing config and re-clone the kit.",
    )
    parser.add_argument(
        "--no-install-kit",
        action="store_true",
        help="Don't auto-install the kit. The path passed via --kit-path must exist.",
    )
    parser.add_argument(
        "--no-scaffolds",
        action="store_true",
        help="Skip slash-command / sub-agent / hook scaffolds.",
    )
    parser.add_argument(
        "--no-doctor",
        action="store_true",
        help="Skip the doctor smoke check at the end.",
    )


__all__ = [
    "Agent",
    "InitResult",
    "InstallError",
    "add_init_args",
    "detect_agents",
    "install_kit",
    "patch_mcp_json",
    "run_init",
    "run_init_cli",
    "write_default_config",
]
