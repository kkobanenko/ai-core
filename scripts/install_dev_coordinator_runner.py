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
_DEFAULT_BRIDGE_PREFIX = "coord/bridge/"
_DEFAULT_POLL_INTERVAL = 15

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


def install_runner(
    *,
    coordinator_repo: Path,
    managed_worktree_root: Path,
    repositories: dict[str, Path],
    python_bin: Optional[str] = None,
    agent_bin: Optional[str] = None,
    poll_interval: int = _DEFAULT_POLL_INTERVAL,
    enable: bool = False,
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

    if enable:
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
        help="Run systemctl --user daemon-reload and enable --now",
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
        outcome = install_runner(
            coordinator_repo=args.coordinator_repo,
            managed_worktree_root=args.managed_worktree_root,
            repositories=repos,
            python_bin=args.python_bin,
            agent_bin=args.agent_bin,
            poll_interval=args.poll_interval,
            enable=args.enable,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"install failed: {exc}", file=sys.stderr)
        return 2

    print(f"config: {outcome['config_path']}")
    print(f"unit: {outcome['unit_path']}")
    print(f"enabled: {outcome['enabled']}")
    if outcome["enabled"] == "true":
        print(f"status: systemctl --user status {_SERVICE_NAME} --no-pager")
        print(
            f"logs: journalctl --user -u {_SERVICE_NAME} -n 100 --no-pager"
        )
    else:
        print(
            "service not enabled; re-run with --enable after review"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
