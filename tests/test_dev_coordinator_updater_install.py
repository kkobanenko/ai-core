"""Тесты installer extension для updater (без live timer enable)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.install_dev_coordinator_runner import (
    install_runner,
    render_updater_timer,
    render_updater_unit,
)


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / ".local" / "state"))
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


def test_first_install_writes_updater_artifacts(fake_home: Path) -> None:
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
        enable_updater=False,
        systemctl_runner=fake_systemctl,
    )

    updater_config = Path(outcome["updater_config_path"])
    updater_service = Path(outcome["updater_service_path"])
    updater_timer = Path(outcome["updater_timer_path"])
    assert updater_config.is_file()
    assert updater_service.is_file()
    assert updater_timer.is_file()
    assert systemctl_calls == []
    assert outcome["updater_enabled"] == "false"

    data = json.loads(updater_config.read_text(encoding="utf-8"))
    assert data["coordinator_repo_root"] == str(paths["coord"])
    assert data["timer_interval_seconds"] == 60
    assert data["transition_branch"] == "chore/coordinator-transition-v0.1-20260911"

    runner_config = json.loads(Path(outcome["config_path"]).read_text(encoding="utf-8"))
    assert runner_config["coordinator_repo_root"] == str(paths["coord"])


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
    assert Path(outcome2["updater_config_path"]).is_file()


def test_enable_updater_invokes_systemctl(fake_home: Path) -> None:
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
        enable_updater=True,
        systemctl_runner=fake_systemctl,
    )
    assert outcome["updater_enabled"] == "true"
    assert ["daemon-reload"] in calls
    assert ["enable", "--now", "ai-core-dev-coordinator-updater.timer"] in calls


def test_rendered_updater_units(fake_home: Path) -> None:
    paths = _layout(fake_home)
    config_path = fake_home / ".config" / "ai-core-dev-coordinator" / "updater.json"
    service = render_updater_unit(
        python_bin=paths["python"],
        coordinator_repo=paths["coord"],
        config_path=config_path,
    )
    timer = render_updater_timer(timer_interval=60)
    assert str(paths["python"]) in service
    assert str(paths["coord"]) in service
    assert str(config_path) in service
    assert "Type=oneshot" in service
    assert "--once" in service
    assert "OnUnitActiveSec=60s" in timer


def test_invalid_updater_interval_rejected(fake_home: Path) -> None:
    paths = _layout(fake_home)
    from scripts.install_dev_coordinator_runner import main

    rc = main(
        [
            "--managed-worktree-root",
            str(paths["managed"]),
            "--repo",
            f"kkobanenko/ai-core={paths['ai_core']}",
            "--python-bin",
            str(paths["python"]),
            "--agent-bin",
            str(paths["agent"]),
            "--updater-timer-interval",
            "10",
        ]
    )
    assert rc == 2
