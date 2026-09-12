#!/usr/bin/env python3
"""Идемпотентный установщик persistent Coordinator runner (user systemd)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional, Sequence

# Корень репозитория Coordinator (где лежит tools/).
_REPO_ROOT = Path(__file__).resolve().parents[1]

_SERVICE_NAME = "ai-core-dev-coordinator-runner.service"
_UNIT_TEMPLATE = (
    _REPO_ROOT / "ops" / "systemd" / "ai-core-dev-coordinator-runner.service.in"
)
_UPDATER_SERVICE_NAME = "ai-core-dev-coordinator-updater.service"
_UPDATER_TIMER_NAME = "ai-core-dev-coordinator-updater.timer"
_UPDATER_UNIT_TEMPLATE = (
    _REPO_ROOT / "ops" / "systemd" / "ai-core-dev-coordinator-updater.service.in"
)
_UPDATER_TIMER_TEMPLATE = (
    _REPO_ROOT / "ops" / "systemd" / "ai-core-dev-coordinator-updater.timer.in"
)
_DEFAULT_BRIDGE_PREFIX = "coord/bridge/"
_DEFAULT_POLL_INTERVAL = 15
_DEFAULT_TRANSITION_BRANCH = "chore/coordinator-transition-v0.1-20260911"
_DEFAULT_ORIGIN_URL = "https://github.com/kkobanenko/ai-core.git"
_DEFAULT_UPDATER_INTERVAL = 60

SystemctlRunner = Callable[[Sequence[str]], tuple[int, str, str]]


def _default_systemctl(args: Sequence[str]) -> tuple[int, str, str]:
    """Вызов systemctl --user (можно подменить в тестах)."""
    proc = subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg).expanduser()
    else:
        base = Path.home() / ".config"
    return (base / "ai-core-dev-coordinator").resolve()


def _systemd_user_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg).expanduser()
    else:
        base = Path.home() / ".config"
    return (base / "systemd" / "user").resolve()


def _resolve_python(explicit: Optional[str]) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"python binary not found: {path}")
        return path
    found = shutil.which("python3.10") or shutil.which("python3")
    if not found:
        raise ValueError("unable to locate python3.10 or python3 on PATH")
    return Path(found).resolve()


def _resolve_agent(explicit: Optional[str]) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"agent binary not found: {path}")
        return path
    found = shutil.which("agent")
    if not found:
        raise ValueError("unable to locate agent on PATH; pass --agent-bin")
    return Path(found).resolve()


def _parse_repo_arg(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"--repo expects OWNER/REPO=PATH, got {value!r}")
    name, path_str = value.split("=", 1)
    name = name.strip()
    path = Path(path_str.strip()).expanduser().resolve()
    if "/" not in name:
        raise ValueError(f"invalid repo name: {name!r}")
    if not path.is_dir():
        raise ValueError(f"repository path does not exist: {path}")
    return name, path


def build_config(
    *,
    coordinator_repo: Path,
    managed_worktree_root: Path,
    agent_bin: Path,
    repositories: dict[str, Path],
    poll_interval: int,
) -> dict:
    return {
        "poll_interval_seconds": poll_interval,
        "coordinator_repo_root": str(coordinator_repo),
        "managed_worktree_root": str(managed_worktree_root),
        "agent_bin": str(agent_bin),
        "bridge_prefix": _DEFAULT_BRIDGE_PREFIX,
        "repositories": {k: str(v) for k, v in repositories.items()},
    }


def write_config(config: dict, config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def render_unit(
    *,
    python_bin: Path,
    coordinator_repo: Path,
    config_path: Path,
) -> str:
    template = _UNIT_TEMPLATE.read_text(encoding="utf-8")
    return (
        template.replace("{{PYTHON_BIN}}", str(python_bin))
        .replace("{{COORDINATOR_REPO_ROOT}}", str(coordinator_repo))
        .replace("{{CONFIG_PATH}}", str(config_path))
    )


def write_unit(content: str, unit_path: Path) -> None:
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(content, encoding="utf-8")


def build_updater_config(
    *,
    coordinator_repo: Path,
    transition_branch: str,
    expected_origin_url: str,
    timer_interval: int,
    state_dir: Path,
) -> dict:
    from tools.dev_coordinator.updater_config import default_updater_config_dict

    return default_updater_config_dict(
        coordinator_repo=coordinator_repo,
        transition_branch=transition_branch,
        expected_origin_url=expected_origin_url,
        state_dir=state_dir,
        timer_interval_seconds=timer_interval,
    )


def render_updater_unit(
    *,
    python_bin: Path,
    coordinator_repo: Path,
    config_path: Path,
) -> str:
    template = _UPDATER_UNIT_TEMPLATE.read_text(encoding="utf-8")
    return (
        template.replace("{{PYTHON_BIN}}", str(python_bin))
        .replace("{{COORDINATOR_REPO_ROOT}}", str(coordinator_repo))
        .replace("{{CONFIG_PATH}}", str(config_path))
    )


def render_updater_timer(*, timer_interval: int) -> str:
    template = _UPDATER_TIMER_TEMPLATE.read_text(encoding="utf-8")
    return template.replace("{{TIMER_INTERVAL}}", f"{timer_interval}s")


def install_updater(
    *,
    coordinator_repo: Path,
    transition_branch: str,
    expected_origin_url: str,
    timer_interval: int,
    state_dir: Path,
    python_bin: Path,
) -> dict[str, str]:
    """Установить updater config + units (без systemctl activation)."""
    config = build_updater_config(
        coordinator_repo=coordinator_repo.resolve(),
        transition_branch=transition_branch,
        expected_origin_url=expected_origin_url,
        timer_interval=timer_interval,
        state_dir=state_dir.resolve(),
    )
    config_path = _config_dir() / "updater.json"
    write_config(config, config_path)

    service_content = render_updater_unit(
        python_bin=python_bin,
        coordinator_repo=coordinator_repo.resolve(),
        config_path=config_path,
    )
    service_path = _systemd_user_dir() / _UPDATER_SERVICE_NAME
    write_unit(service_content, service_path)

    timer_content = render_updater_timer(timer_interval=timer_interval)
    timer_path = _systemd_user_dir() / _UPDATER_TIMER_NAME
    write_unit(timer_content, timer_path)

    return {
        "updater_config_path": str(config_path),
        "updater_service_path": str(service_path),
        "updater_timer_path": str(timer_path),
        "updater_enabled": "false",
    }


def _activate_updater_bootstrap(
    systemctl_runner: SystemctlRunner,
) -> None:
    """Fail-closed bootstrap: runner enable+restart, затем updater timer.

    Порядок детерминированный — один daemon-reload и один restart runner
    за вызов. Не полагаемся на enable --now как доказательство re-exec.
    """
    code, out, err = systemctl_runner(["daemon-reload"])
    if code != 0:
        raise RuntimeError(f"systemctl daemon-reload failed: {err or out}")

    code, out, err = systemctl_runner(["enable", _SERVICE_NAME])
    if code != 0:
        raise RuntimeError(f"systemctl enable runner failed: {err or out}")

    code, out, err = systemctl_runner(["restart", _SERVICE_NAME])
    if code != 0:
        raise RuntimeError(f"systemctl restart runner failed: {err or out}")

    code, out, err = systemctl_runner(["enable", "--now", _UPDATER_TIMER_NAME])
    if code != 0:
        raise RuntimeError(
            f"systemctl enable --now updater timer failed: {err or out}"
        )


def install_runner(
    *,
    coordinator_repo: Path,
    managed_worktree_root: Path,
    repositories: dict[str, Path],
    python_bin: Optional[str] = None,
    agent_bin: Optional[str] = None,
    poll_interval: int = _DEFAULT_POLL_INTERVAL,
    enable: bool = False,
    enable_updater: bool = False,
    transition_branch: str = _DEFAULT_TRANSITION_BRANCH,
    expected_origin_url: str = _DEFAULT_ORIGIN_URL,
    updater_timer_interval: int = _DEFAULT_UPDATER_INTERVAL,
    state_dir: Optional[Path] = None,
    systemctl_runner: SystemctlRunner = _default_systemctl,
) -> dict[str, str]:
    """Установить config + unit; опционально enable/start."""
    if not coordinator_repo.is_dir():
        raise ValueError(f"coordinator repo not found: {coordinator_repo}")
    if not managed_worktree_root.is_dir():
        raise ValueError(
            f"managed worktree root not found: {managed_worktree_root}"
        )
    if not repositories:
        raise ValueError("at least one --repo is required")

    py = _resolve_python(python_bin)
    agent = _resolve_agent(agent_bin)

    config = build_config(
        coordinator_repo=coordinator_repo.resolve(),
        managed_worktree_root=managed_worktree_root.resolve(),
        agent_bin=agent,
        repositories=repositories,
        poll_interval=poll_interval,
    )

    config_path = _config_dir() / "runner.json"
    write_config(config, config_path)

    unit_content = render_unit(
        python_bin=py,
        coordinator_repo=coordinator_repo.resolve(),
        config_path=config_path,
    )
    unit_path = _systemd_user_dir() / _SERVICE_NAME
    write_unit(unit_content, unit_path)

    result = {
        "config_path": str(config_path),
        "unit_path": str(unit_path),
        "enabled": "false",
    }

    from tools.dev_coordinator.paths import default_state_dir

    updater_outcome = install_updater(
        coordinator_repo=coordinator_repo.resolve(),
        transition_branch=transition_branch,
        expected_origin_url=expected_origin_url,
        timer_interval=updater_timer_interval,
        state_dir=state_dir or default_state_dir(),
        python_bin=py,
    )
    result.update(updater_outcome)

    if enable_updater:
        # --enable-updater гарантирует runner activation в той же транзакции:
        # enable + explicit restart на новый unit, затем timer (fail-closed).
        _activate_updater_bootstrap(systemctl_runner)
        result["enabled"] = "true"
        result["updater_enabled"] = "true"
    elif enable:
        code, out, err = systemctl_runner(["daemon-reload"])
        if code != 0:
            raise RuntimeError(f"systemctl daemon-reload failed: {err or out}")
        code, out, err = systemctl_runner(
            ["enable", "--now", _SERVICE_NAME]
        )
        if code != 0:
            raise RuntimeError(f"systemctl enable --now failed: {err or out}")
        result["enabled"] = "true"

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install persistent Coordinator runner (user systemd).",
    )
    parser.add_argument(
        "--coordinator-repo",
        type=Path,
        default=_REPO_ROOT,
        help="Coordinator tooling checkout (default: repo containing this script)",
    )
    parser.add_argument(
        "--managed-worktree-root",
        type=Path,
        required=True,
        help="Root for managed bridge/executor worktrees",
    )
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        metavar="OWNER/REPO=PATH",
        help="Allowlisted repository clone (repeatable)",
    )
    parser.add_argument(
        "--agent-bin",
        default=None,
        help="Absolute path to Cursor agent (default: which agent)",
    )
    parser.add_argument(
        "--python-bin",
        default=None,
        help="Python interpreter (default: python3.10 or python3)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=_DEFAULT_POLL_INTERVAL,
        help="Poll interval seconds (default: 15)",
    )
    parser.add_argument(
        "--enable",
        action="store_true",
        help="Run systemctl --user daemon-reload and enable --now runner",
    )
    parser.add_argument(
        "--enable-updater",
        action="store_true",
        help=(
            "Fail-closed updater bootstrap: daemon-reload, enable+restart runner "
            "on reviewed unit, then enable updater timer (implies runner activation)"
        ),
    )
    parser.add_argument(
        "--transition-branch",
        default=_DEFAULT_TRANSITION_BRANCH,
        help="Reviewed transition branch for self-update",
    )
    parser.add_argument(
        "--expected-origin-url",
        default=_DEFAULT_ORIGIN_URL,
        help="Expected origin URL for Coordinator checkout",
    )
    parser.add_argument(
        "--updater-timer-interval",
        type=int,
        default=_DEFAULT_UPDATER_INTERVAL,
        help="Updater timer interval seconds (default: 60, min: 30)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    repos: dict[str, Path] = {}
    for item in args.repo:
        name, path = _parse_repo_arg(item)
        repos[name] = path

    try:
        if args.updater_timer_interval < 30:
            raise ValueError("updater timer interval must be >= 30 seconds")
        outcome = install_runner(
            coordinator_repo=args.coordinator_repo,
            managed_worktree_root=args.managed_worktree_root,
            repositories=repos,
            python_bin=args.python_bin,
            agent_bin=args.agent_bin,
            poll_interval=args.poll_interval,
            enable=args.enable,
            enable_updater=args.enable_updater,
            transition_branch=args.transition_branch,
            expected_origin_url=args.expected_origin_url,
            updater_timer_interval=args.updater_timer_interval,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"install failed: {exc}", file=sys.stderr)
        return 2

    print(f"config: {outcome['config_path']}")
    print(f"unit: {outcome['unit_path']}")
    print(f"enabled: {outcome['enabled']}")
    print(f"updater_config: {outcome['updater_config_path']}")
    print(f"updater_service: {outcome['updater_service_path']}")
    print(f"updater_timer: {outcome['updater_timer_path']}")
    print(f"updater_enabled: {outcome['updater_enabled']}")
    if outcome["enabled"] == "true":
        print(f"status: systemctl --user status {_SERVICE_NAME} --no-pager")
        print(
            f"logs: journalctl --user -u {_SERVICE_NAME} -n 100 --no-pager"
        )
    else:
        print(
            "service not enabled; re-run with --enable after review"
        )
    if outcome["updater_enabled"] != "true":
        print(
            "updater timer not enabled; re-run with --enable-updater after review"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
