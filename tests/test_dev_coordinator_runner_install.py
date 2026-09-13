"""Тесты install_dev_coordinator_runner (без реального systemctl enable)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.install_dev_coordinator_runner import (
    build_config,
    install_runner,
    render_unit,
)


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    return tmp_path


def _layout(home: Path) -> dict[str, Path]:
    coord = home / "coord"
    managed = home / "worktrees"
    ai_core = home / "ai-core"
    agent = home / "bin" / "agent"
    for d in (coord, managed, ai_core, agent.parent):
        d.mkdir(parents=True)
    agent.write_text("#!/bin/sh\n", encoding="utf-8")
    agent.chmod(0o755)
    python = home / "bin" / "python3"
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    python.chmod(0o755)
    return {
        "coord": coord,
        "managed": managed,
        "ai_core": ai_core,
        "agent": agent,
        "python": python,
    }


def test_first_install_writes_config_and_unit(fake_home: Path) -> None:
    paths = _layout(fake_home)
    systemctl_calls: list[list[str]] = []

    def fake_systemctl(args):
        systemctl_calls.append(list(args))
        return 0, "", ""

    outcome = install_runner(
        coordinator_repo=paths["coord"],
        managed_worktree_root=paths["managed"],
        repositories={"kkobanenko/ai-core": paths["ai_core"]},
        python_bin=str(paths["python"]),
        agent_bin=str(paths["agent"]),
        enable=False,
        systemctl_runner=fake_systemctl,
    )

    config_path = Path(outcome["config_path"])
    unit_path = Path(outcome["unit_path"])
    assert config_path.is_file()
    assert unit_path.is_file()
    assert systemctl_calls == []
    assert outcome["enabled"] == "false"

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["bridge_prefix"] == "coord/bridge/"
    assert data["repositories"]["kkobanenko/ai-core"] == str(paths["ai_core"])


def test_idempotent_reinstall(fake_home: Path) -> None:
    paths = _layout(fake_home)

    def fake_systemctl(args):
        return 0, "", ""

    install_runner(
        coordinator_repo=paths["coord"],
        managed_worktree_root=paths["managed"],
        repositories={"kkobanenko/ai-core": paths["ai_core"]},
        python_bin=str(paths["python"]),
        agent_bin=str(paths["agent"]),
        enable=False,
        systemctl_runner=fake_systemctl,
    )
    outcome2 = install_runner(
        coordinator_repo=paths["coord"],
        managed_worktree_root=paths["managed"],
        repositories={"kkobanenko/ai-core": paths["ai_core"]},
        python_bin=str(paths["python"]),
        agent_bin=str(paths["agent"]),
        enable=False,
        systemctl_runner=fake_systemctl,
    )
    assert Path(outcome2["config_path"]).is_file()


def test_enable_invokes_systemctl(fake_home: Path) -> None:
    paths = _layout(fake_home)
    calls: list[list[str]] = []

    def fake_systemctl(args):
        calls.append(list(args))
        return 0, "", ""

    outcome = install_runner(
        coordinator_repo=paths["coord"],
        managed_worktree_root=paths["managed"],
        repositories={"kkobanenko/ai-core": paths["ai_core"]},
        python_bin=str(paths["python"]),
        agent_bin=str(paths["agent"]),
        enable=True,
        systemctl_runner=fake_systemctl,
    )
    assert outcome["enabled"] == "true"
    assert ["daemon-reload"] in calls
    assert ["enable", "--now", "ai-core-dev-coordinator-runner.service"] in calls


def test_invalid_agent_path(fake_home: Path) -> None:
    paths = _layout(fake_home)
    with pytest.raises(ValueError, match="agent binary not found"):
        install_runner(
            coordinator_repo=paths["coord"],
            managed_worktree_root=paths["managed"],
            repositories={"kkobanenko/ai-core": paths["ai_core"]},
            python_bin=str(paths["python"]),
            agent_bin=str(fake_home / "missing-agent"),
            enable=False,
        )


def test_rendered_unit_contains_absolute_paths(fake_home: Path) -> None:
    paths = _layout(fake_home)
    config_path = fake_home / ".config" / "ai-core-dev-coordinator" / "runner.json"
    content = render_unit(
        python_bin=paths["python"],
        coordinator_repo=paths["coord"],
        config_path=config_path,
    )
    assert str(paths["python"]) in content
    assert str(paths["coord"]) in content
    assert str(config_path) in content
    assert "Restart=on-failure" in content
