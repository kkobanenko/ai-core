"""Тесты installer extension для updater (без live timer enable)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.install_dev_coordinator_runner import (
    _REPO_ROOT,
    _SERVICE_NAME,
    _UPDATER_TIMER_NAME,
    install_runner,
    render_updater_timer,
    render_updater_unit,
)

_INSTALLER_SCRIPT = _REPO_ROOT / "scripts" / "install_dev_coordinator_runner.py"


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


def test_enable_updater_restarts_runner_before_timer(fake_home: Path) -> None:
    """Updater bootstrap: explicit runner restart before timer enable."""
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
    assert outcome["enabled"] == "true"
    assert calls == [
        ["daemon-reload"],
        ["enable", _SERVICE_NAME],
        ["restart", _SERVICE_NAME],
        ["enable", "--now", _UPDATER_TIMER_NAME],
    ]


def test_enable_updater_with_enable_single_restart(fake_home: Path) -> None:
    """--enable + --enable-updater: один restart, без enable --now runner."""
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
        enable_updater=True,
        systemctl_runner=fake_systemctl,
    )
    assert outcome["enabled"] == "true"
    assert outcome["updater_enabled"] == "true"
    assert calls.count(["restart", _SERVICE_NAME]) == 1
    assert ["enable", "--now", _SERVICE_NAME] not in calls
    assert calls == [
        ["daemon-reload"],
        ["enable", _SERVICE_NAME],
        ["restart", _SERVICE_NAME],
        ["enable", "--now", _UPDATER_TIMER_NAME],
    ]


def test_enable_updater_daemon_reload_failure_blocks_activation(
    fake_home: Path,
) -> None:
    paths = _layout(fake_home)
    calls: list[list[str]] = []

    def fake_systemctl(args):
        if args == ["daemon-reload"]:
            return 1, "", "reload failed"
        calls.append(list(args))
        return 0, "", ""

    with pytest.raises(RuntimeError, match="daemon-reload"):
        install_runner(
            coordinator_repo=paths["coord"],
            managed_worktree_root=paths["managed"],
            repositories={"kkobanenko/ai-core": paths["ai_core"]},
            python_bin=str(paths["python"]),
            agent_bin=str(paths["agent"]),
            enable_updater=True,
            systemctl_runner=fake_systemctl,
        )
    assert calls == []


def test_enable_updater_runner_restart_failure_blocks_timer(
    fake_home: Path,
) -> None:
    paths = _layout(fake_home)
    calls: list[list[str]] = []

    def fake_systemctl(args):
        calls.append(list(args))
        if args == ["restart", _SERVICE_NAME]:
            return 1, "", "restart failed"
        return 0, "", ""

    with pytest.raises(RuntimeError, match="restart runner"):
        install_runner(
            coordinator_repo=paths["coord"],
            managed_worktree_root=paths["managed"],
            repositories={"kkobanenko/ai-core": paths["ai_core"]},
            python_bin=str(paths["python"]),
            agent_bin=str(paths["agent"]),
            enable_updater=True,
            systemctl_runner=fake_systemctl,
        )
    assert ["enable", "--now", _UPDATER_TIMER_NAME] not in calls


def test_enable_updater_timer_enable_failure_surfaces_error(
    fake_home: Path,
) -> None:
    paths = _layout(fake_home)
    calls: list[list[str]] = []

    def fake_systemctl(args):
        calls.append(list(args))
        if args == ["enable", "--now", _UPDATER_TIMER_NAME]:
            return 1, "", "timer failed"
        return 0, "", ""

    with pytest.raises(RuntimeError, match="updater timer"):
        install_runner(
            coordinator_repo=paths["coord"],
            managed_worktree_root=paths["managed"],
            repositories={"kkobanenko/ai-core": paths["ai_core"]},
            python_bin=str(paths["python"]),
            agent_bin=str(paths["agent"]),
            enable_updater=True,
            systemctl_runner=fake_systemctl,
        )
    assert ["restart", _SERVICE_NAME] in calls
    assert calls.count(["enable", "--now", _UPDATER_TIMER_NAME]) == 1


def test_enable_updater_idempotent_single_restart_per_invocation(
    fake_home: Path,
) -> None:
    paths = _layout(fake_home)
    calls: list[list[str]] = []

    def fake_systemctl(args):
        calls.append(list(args))
        return 0, "", ""

    install_runner(
        coordinator_repo=paths["coord"],
        managed_worktree_root=paths["managed"],
        repositories={"kkobanenko/ai-core": paths["ai_core"]},
        python_bin=str(paths["python"]),
        agent_bin=str(paths["agent"]),
        enable_updater=True,
        systemctl_runner=fake_systemctl,
    )
    first_restart_count = calls.count(["restart", _SERVICE_NAME])
    assert first_restart_count == 1

    install_runner(
        coordinator_repo=paths["coord"],
        managed_worktree_root=paths["managed"],
        repositories={"kkobanenko/ai-core": paths["ai_core"]},
        python_bin=str(paths["python"]),
        agent_bin=str(paths["agent"]),
        enable_updater=True,
        systemctl_runner=fake_systemctl,
    )
    assert calls.count(["restart", _SERVICE_NAME]) == 2


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


def _run_installer_subprocess(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Запуск installer как отдельного процесса (без PYTHONPATH)."""
    run_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    if env is not None:
        run_env.update(env)
    return subprocess.run(
        [sys.executable, str(_INSTALLER_SCRIPT), *args],
        cwd=str(cwd),
        env=run_env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_direct_invocation_help_from_outside_repo(tmp_path: Path) -> None:
    """Регрессия: абсолютный путь к скрипту без PYTHONPATH и вне репозитория."""
    outside = tmp_path / "outside"
    outside.mkdir()
    proc = _run_installer_subprocess(["--help"], cwd=outside)
    assert proc.returncode == 0, proc.stderr
    assert "Install persistent Coordinator runner" in proc.stdout


def test_direct_invocation_config_path_without_pythonpath(
    fake_home: Path,
) -> None:
    """Регрессия: неактивирующий install из cwd вне репозитория без PYTHONPATH."""
    paths = _layout(fake_home)
    outside = fake_home / "outside"
    outside.mkdir()
    proc = _run_installer_subprocess(
        [
            "--coordinator-repo",
            str(_REPO_ROOT),
            "--managed-worktree-root",
            str(paths["managed"]),
            "--repo",
            f"kkobanenko/ai-core={paths['ai_core']}",
            "--python-bin",
            str(paths["python"]),
            "--agent-bin",
            str(paths["agent"]),
        ],
        cwd=outside,
    )
    assert proc.returncode == 0, proc.stderr
    assert "config:" in proc.stdout
    assert "updater_config:" in proc.stdout
    assert "service not enabled" in proc.stdout


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
