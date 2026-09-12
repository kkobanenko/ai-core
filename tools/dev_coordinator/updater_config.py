"""Строгий JSON-парсер конфигурации self-update updater (только stdlib)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from tools.dev_coordinator.gitutil import canonicalize_github_repo
from tools.dev_coordinator.paths import default_state_dir

# Разрешённые ключи верхнего уровня (fail closed на неизвестные).
_ALLOWED_TOP_KEYS = frozenset(
    {
        "coordinator_repo_root",
        "transition_branch",
        "expected_origin_url",
        "runner_service",
        "timer_interval_seconds",
        "state_dir",
    }
)

# Запрещённые имена transition-веток.
_FORBIDDEN_BRANCHES = frozenset({"main", "master"})

# Минимальный интервал таймера (секунды).
_MIN_TIMER_INTERVAL = 30
_DEFAULT_TIMER_INTERVAL = 60

_DEFAULT_RUNNER_SERVICE = "ai-core-dev-coordinator-runner.service"


@dataclass(frozen=True)
class UpdaterConfig:
    """Валидированная конфигурация self-update updater."""

    coordinator_repo_root: Path
    transition_branch: str
    expected_origin_url: str
    runner_service: str
    timer_interval_seconds: int
    state_dir: Path

    @property
    def expected_origin_identity(self) -> str:
        """Канонический OWNER/REPO или нормализованный URL для сравнения."""
        canonical = canonicalize_github_repo(self.expected_origin_url)
        if canonical:
            return canonical
        return self.expected_origin_url.strip().rstrip("/")


def _parse_absolute_path(raw: Any, label: str) -> Path:
    """Развернуть ~ и отклонить относительные пути."""
    path = Path(str(raw)).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path: {path}")
    return path.resolve()


def _require_absolute_existing_dir(path: Path, label: str) -> None:
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path: {path}")
    if not path.is_dir():
        raise ValueError(f"{label} does not exist or is not a directory: {path}")


def _validate_transition_branch(branch: Any) -> str:
    if not isinstance(branch, str):
        raise ValueError("transition_branch must be a string")
    name = branch.strip()
    if not name:
        raise ValueError("transition_branch must be non-empty")
    if name in _FORBIDDEN_BRANCHES:
        raise ValueError(f"transition_branch must not be {name!r}")
    return name


def _validate_expected_origin(url: Any) -> str:
    if not isinstance(url, str):
        raise ValueError("expected_origin_url must be a string")
    value = url.strip()
    if not value:
        raise ValueError("expected_origin_url must be non-empty")
    return value


def parse_updater_config(data: Mapping[str, Any]) -> UpdaterConfig:
    """Разобрать dict конфигурации с жёсткой валидацией."""
    unknown = set(data.keys()) - _ALLOWED_TOP_KEYS
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}")

    for required in _ALLOWED_TOP_KEYS:
        if required not in data:
            raise ValueError(f"missing required config key: {required}")

    coordinator_root = _parse_absolute_path(
        data["coordinator_repo_root"], "coordinator_repo_root"
    )
    _require_absolute_existing_dir(coordinator_root, "coordinator_repo_root")

    transition_branch = _validate_transition_branch(data["transition_branch"])
    expected_origin_url = _validate_expected_origin(data["expected_origin_url"])

    runner_service = data["runner_service"]
    if not isinstance(runner_service, str) or not runner_service.strip():
        raise ValueError("runner_service must be a non-empty string")
    runner_service = runner_service.strip()

    timer = data["timer_interval_seconds"]
    if not isinstance(timer, int) or isinstance(timer, bool):
        raise ValueError("timer_interval_seconds must be an integer")
    if timer < _MIN_TIMER_INTERVAL:
        raise ValueError(
            f"timer_interval_seconds must be >= {_MIN_TIMER_INTERVAL}, got {timer}"
        )

    state_dir = _parse_absolute_path(data["state_dir"], "state_dir")
    # state_dir может ещё не существовать — создаётся ensure_state_layout.
    if not state_dir.is_absolute():
        raise ValueError(f"state_dir must be an absolute path: {state_dir}")

    return UpdaterConfig(
        coordinator_repo_root=coordinator_root,
        transition_branch=transition_branch,
        expected_origin_url=expected_origin_url,
        runner_service=runner_service,
        timer_interval_seconds=timer,
        state_dir=state_dir,
    )


def validate_against_runner_config(
    updater: UpdaterConfig,
    runner_config_path: Path,
) -> None:
    """Сверить coordinator_repo_root с runner.json, если оба присутствуют."""
    if not runner_config_path.is_file():
        return
    from tools.dev_coordinator.runner_config import load_runner_config

    runner = load_runner_config(runner_config_path)
    if runner.coordinator_repo_root != updater.coordinator_repo_root:
        raise ValueError(
            "coordinator_repo_root mismatch between updater.json and runner.json: "
            f"updater={updater.coordinator_repo_root} "
            f"runner={runner.coordinator_repo_root}"
        )


def load_updater_config(
    path: Path,
    *,
    runner_config_path: Optional[Path] = None,
) -> UpdaterConfig:
    """Загрузить конфигурацию из JSON-файла."""
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in config {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("updater config root must be a JSON object")
    config = parse_updater_config(data)
    if runner_config_path is not None:
        validate_against_runner_config(config, runner_config_path)
    return config


def default_config_path() -> Path:
    """Путь по умолчанию: ~/.config/ai-core-dev-coordinator/updater.json."""
    import os

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg).expanduser()
    else:
        base = Path.home() / ".config"
    return (base / "ai-core-dev-coordinator" / "updater.json").resolve()


def default_updater_config_dict(
    *,
    coordinator_repo: Path,
    transition_branch: str,
    expected_origin_url: str,
    state_dir: Optional[Path] = None,
    runner_service: str = _DEFAULT_RUNNER_SERVICE,
    timer_interval_seconds: int = _DEFAULT_TIMER_INTERVAL,
) -> dict[str, Any]:
    """Собрать dict конфигурации для installer."""
    return {
        "coordinator_repo_root": str(coordinator_repo.resolve()),
        "transition_branch": transition_branch,
        "expected_origin_url": expected_origin_url,
        "runner_service": runner_service,
        "timer_interval_seconds": timer_interval_seconds,
        "state_dir": str((state_dir or default_state_dir()).resolve()),
    }
