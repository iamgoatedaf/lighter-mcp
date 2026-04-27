"""Tests for the ``lighter-mcp init`` orchestrator.

These tests are hermetic: they never touch the network, never require the
real ``lighter-agent-kit`` checkout, and don't mutate the user's home
directory. The kit auto-clone path is exercised separately in
``test_install_kit_local`` using a tarball assembled on the fly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lighter_mcp import installer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_kit(root: Path) -> Path:
    """Create a minimal directory that satisfies ``install_kit``'s sanity check."""
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts" / "query.py").write_text(
        "#!/usr/bin/env python3\nprint('{}')\n"
    )
    return root


# ---------------------------------------------------------------------------
# detect_agents
# ---------------------------------------------------------------------------


def test_detect_agents_returns_only_present(tmp_path, monkeypatch):
    """An agent appears in the result iff its config dir already exists."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)

    # No agents installed yet → empty result
    assert installer.detect_agents() == []

    # Adding ~/.cursor surfaces Cursor (user-scope).
    (home / ".cursor").mkdir()
    names = [a.name for a in installer.detect_agents()]
    assert names == ["cursor"]

    # Adding ~/.codex surfaces Codex too.
    (home / ".codex").mkdir()
    names = sorted(a.name for a in installer.detect_agents())
    assert names == ["codex", "cursor"]


def test_detect_agents_includes_project_cursor(tmp_path, monkeypatch):
    """Project-scoped Cursor is offered when the project has a .cursor dir."""
    home = tmp_path / "home"
    project = tmp_path / "proj"
    (home / ".cursor").mkdir(parents=True)
    (project / ".cursor").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)

    found = installer.detect_agents(project_dir=project)
    cursor_scopes = sorted(a.scope for a in found if a.name == "cursor")
    assert cursor_scopes == ["project", "user"]


# ---------------------------------------------------------------------------
# patch_mcp_json
# ---------------------------------------------------------------------------


def test_patch_mcp_json_creates_file(tmp_path):
    cfg = tmp_path / ".cursor" / "mcp.json"
    installer.patch_mcp_json(
        cfg,
        command="/usr/local/bin/lighter-mcp",
        lighter_config=Path("/home/u/.lighter/lighter-mcp/config.toml"),
    )
    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["lighter"]["command"] == "/usr/local/bin/lighter-mcp"
    assert data["mcpServers"]["lighter"]["args"] == ["stdio"]
    assert (
        data["mcpServers"]["lighter"]["env"]["LIGHTER_MCP_CONFIG"]
        == "/home/u/.lighter/lighter-mcp/config.toml"
    )


def test_patch_mcp_json_preserves_unrelated_servers(tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))

    installer.patch_mcp_json(
        cfg,
        command="lighter-mcp",
        lighter_config=Path("/c/cfg.toml"),
    )
    data = json.loads(cfg.read_text())
    assert "other" in data["mcpServers"]
    assert data["mcpServers"]["other"]["command"] == "x"
    assert "lighter" in data["mcpServers"]


def test_patch_mcp_json_alternate_shape(tmp_path):
    """Some agents nest under ``mcp.servers`` instead of ``mcpServers``."""
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcp": {"servers": {"keep": {"command": "k"}}}}))
    installer.patch_mcp_json(
        cfg,
        command="lighter-mcp",
        lighter_config=Path("/c/cfg.toml"),
    )
    data = json.loads(cfg.read_text())
    assert "lighter" in data["mcp"]["servers"]
    assert "keep" in data["mcp"]["servers"]


def test_patch_mcp_json_quarantines_invalid(tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text("{not json")
    installer.patch_mcp_json(
        cfg,
        command="lighter-mcp",
        lighter_config=Path("/c/cfg.toml"),
    )
    assert cfg.with_suffix(cfg.suffix + ".bak").exists()
    data = json.loads(cfg.read_text())
    assert "lighter" in data["mcpServers"]


def test_patch_mcp_json_refuses_non_dict_servers(tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": ["lol"]}))
    with pytest.raises(installer.InstallError):
        installer.patch_mcp_json(
            cfg,
            command="lighter-mcp",
            lighter_config=Path("/c/cfg.toml"),
        )


# ---------------------------------------------------------------------------
# write_default_config
# ---------------------------------------------------------------------------


def test_write_default_config_writes_toml(tmp_path):
    target = tmp_path / "config.toml"
    installer.write_default_config(
        target=target,
        kit_path=Path("/opt/kit"),
        python_executable=Path("/usr/bin/python3"),
        mode="paper",
    )
    body = target.read_text()
    assert 'mode = "paper"' in body
    assert "/opt/kit" in body
    assert "/usr/bin/python3" in body


def test_write_default_config_does_not_clobber(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text('mode = "live"\n')
    installer.write_default_config(
        target=target,
        kit_path=Path("/opt/kit"),
        python_executable=Path("/usr/bin/python3"),
        mode="readonly",
    )
    assert target.read_text() == 'mode = "live"\n'


def test_write_default_config_force_overwrites(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text('mode = "live"\n')
    installer.write_default_config(
        target=target,
        kit_path=Path("/opt/kit"),
        python_executable=Path("/usr/bin/python3"),
        mode="readonly",
        force=True,
    )
    assert 'mode = "readonly"' in target.read_text()


# ---------------------------------------------------------------------------
# install_kit
# ---------------------------------------------------------------------------


def test_install_kit_skips_when_already_present(tmp_path):
    kit = _make_fake_kit(tmp_path / "kit")
    # No mocks: the function should short-circuit before touching the network
    # because scripts/query.py exists.
    result = installer.install_kit(kit)
    assert result == kit
    assert (kit / "scripts" / "query.py").is_file()


def test_install_kit_force_re_runs(tmp_path, monkeypatch):
    """``--force`` should remove the existing dir and re-run the clone path."""
    kit = _make_fake_kit(tmp_path / "kit")
    calls: list[tuple[str, Path]] = []

    def fake_clone(url: str, dest: Path) -> None:
        calls.append((url, dest))
        _make_fake_kit(dest)

    monkeypatch.setattr(installer, "_has_git", lambda: True)
    monkeypatch.setattr(installer, "_git_clone", fake_clone)

    installer.install_kit(kit, force=True)
    assert len(calls) == 1
    assert calls[0][1] == kit


def test_install_kit_uses_tarball_when_no_git(tmp_path, monkeypatch):
    target = tmp_path / "kit"
    monkeypatch.setattr(installer, "_has_git", lambda: False)

    def fake_tarball(url: str, dest: Path) -> None:
        _make_fake_kit(dest)

    monkeypatch.setattr(installer, "_download_tarball", fake_tarball)
    result = installer.install_kit(target)
    assert (result / "scripts" / "query.py").is_file()


def test_install_kit_raises_when_layout_invalid(tmp_path, monkeypatch):
    target = tmp_path / "kit"
    monkeypatch.setattr(installer, "_has_git", lambda: True)

    def broken_clone(url: str, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)  # but no scripts/query.py

    monkeypatch.setattr(installer, "_git_clone", broken_clone)
    with pytest.raises(installer.InstallError):
        installer.install_kit(target)


# ---------------------------------------------------------------------------
# run_init end-to-end (with all I/O mocked except filesystem under tmp)
# ---------------------------------------------------------------------------


def test_run_init_end_to_end(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".cursor").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)

    kit = _make_fake_kit(tmp_path / "kit")
    install_root = tmp_path / "install-root"

    result = installer.run_init(
        install_root=install_root,
        kit_path=kit,
        mode="readonly",
        agents=["cursor"],
        project_dir=tmp_path / "no-such-project",
        auto_install_kit=False,  # kit already exists; don't try to clone
        skip_scaffolds=True,     # adapters dir is not under tmp
    )

    assert result.config_path == install_root / "config.toml"
    assert (install_root / "config.toml").is_file()
    cursor_cfg = home / ".cursor" / "mcp.json"
    assert cursor_cfg.is_file()
    data = json.loads(cursor_cfg.read_text())
    assert "lighter" in data["mcpServers"]
    assert "cursor:user" in result.patched_agents


def test_run_init_skips_unknown_agents(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".cursor").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)

    kit = _make_fake_kit(tmp_path / "kit")
    install_root = tmp_path / "install-root"

    with pytest.raises(installer.InstallError):
        installer.run_init(
            install_root=install_root,
            kit_path=kit,
            agents=["banana"],
            auto_install_kit=False,
            skip_scaffolds=True,
        )
