"""Строгий JSON-парсер конфигурации persistent runner (только stdlib)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

# Разрешённые ключи верхнего уровня (fail closed на неизвестные).
_ALLOWED_TOP_KEYS = frozenset(
    {
        "poll_interval_seconds",
        "coordinator_repo_root",
        "managed_worktree_root",
        "agent_bin",
        "bridge_prefix",
        "repositories",
    }
)

# Единственный поддерживаемый префикс bridge-веток.
REQUIRED_BRIDGE_PREFIX = "coord/bridge/"

# Диапазон интервала опроса (секунды).
_MIN_POLL_INTERVAL = 5
_MAX_POLL_INTERVAL = 300


@dataclass(frozen=True)
class RunnerConfig:
    """Валидированная конфигурация persistent runner."""

    poll_interval_seconds: int
    coordinator_repo_root: Path
    managed_worktree_root: Path
    agent_bin: Path
    bridge_prefix: str
    repositories: dict[str, Path]

    def repo_path(self, canonical_name: str) -> Path | None:
        """Вернуть локальный clone для OWNER/REPO или None."""
        return self.repositories.get(canonical_name)


def _require_absolute_existing_dir(path: Path, label: str) -> None:
    """Проверить, что путь абсолютный и существует как каталог."""
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path: {path}")
    if not path.is_dir():
        raise ValueError(f"{label} does not exist or is not a directory: {path}")


def _require_absolute_existing_file(path: Path, label: str) -> None:
    """Проверить, что путь абсолютный и существует как файл."""
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path: {path}")
    if not path.is_file():
        raise ValueError(f"{label} does not exist or is not a file: {path}")


def parse_runner_config(data: Mapping[str, Any]) -> RunnerConfig:
    """Разобрать dict конфигурации с жёсткой валидацией."""
    unknown = set(data.keys()) - _ALLOWED_TOP_KEYS
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}")

    for required in _ALLOWED_TOP_KEYS:
        if required not in data:
            raise ValueError(f"missing required config key: {required}")

    poll = data["poll_interval_seconds"]
    if not isinstance(poll, int) or isinstance(poll, bool):
        raise ValueError("poll_interval_seconds must be an integer")
    if poll < _MIN_POLL_INTERVAL or poll > _MAX_POLL_INTERVAL:
        raise ValueError(
            f"poll_interval_seconds must be between {_MIN_POLL_INTERVAL} "
            f"and {_MAX_POLL_INTERVAL}, got {poll}"
        )

    bridge_prefix = data["bridge_prefix"]
    if bridge_prefix != REQUIRED_BRIDGE_PREFIX:
        raise ValueError(
            f"bridge_prefix must be exactly '{REQUIRED_BRIDGE_PREFIX}', "
            f"got {bridge_prefix!r}"
        )

    coordinator_root = Path(str(data["coordinator_repo_root"])).expanduser().resolve()
    _require_absolute_existing_dir(coordinator_root, "coordinator_repo_root")

    managed_root = Path(str(data["managed_worktree_root"])).expanduser().resolve()
    _require_absolute_existing_dir(managed_root, "managed_worktree_root")

    agent_bin = Path(str(data["agent_bin"])).expanduser().resolve()
    _require_absolute_existing_file(agent_bin, "agent_bin")

    repos_raw = data["repositories"]
    if not isinstance(repos_raw, dict) or not repos_raw:
        raise ValueError("repositories must be a non-empty object")

    repositories: dict[str, Path] = {}
    seen_paths: dict[Path, str] = {}

    for repo_name, clone_path_raw in repos_raw.items():
        if not isinstance(repo_name, str) or "/" not in repo_name:
            raise ValueError(f"invalid repository key: {repo_name!r}")
        clone_path = Path(str(clone_path_raw)).expanduser().resolve()
        _require_absolute_existing_dir(clone_path, f"repositories[{repo_name}]")
        if clone_path in seen_paths:
            raise ValueError(
                f"duplicate repository clone path: {clone_path} "
                f"({seen_paths[clone_path]} and {repo_name})"
            )
        seen_paths[clone_path] = repo_name
        repositories[repo_name] = clone_path

    return RunnerConfig(
        poll_interval_seconds=poll,
        coordinator_repo_root=coordinator_root,
        managed_worktree_root=managed_root,
        agent_bin=agent_bin,
        bridge_prefix=bridge_prefix,
        repositories=repositories,
    )


def load_runner_config(path: Path) -> RunnerConfig:
    """Загрузить конфигурацию из JSON-файла."""
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in config {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("runner config root must be a JSON object")
    return parse_runner_config(data)


def default_config_path() -> Path:
    """Путь по умолчанию: ~/.config/ai-core-dev-coordinator/runner.json."""
    import os

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg).expanduser()
    else:
        base = Path.home() / ".config"
    return (base / "ai-core-dev-coordinator" / "runner.json").resolve()
