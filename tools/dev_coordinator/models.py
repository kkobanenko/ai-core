"""Модели состояния Coordinator v0.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class CoordState(str, Enum):
    """Разрешённые состояния v0.1."""

    WAIT = "WAIT"
    EXECUTOR_READY = "EXECUTOR_READY"
    EXECUTOR_RUNNING = "EXECUTOR_RUNNING"
    ARCHITECT_REVIEW = "ARCHITECT_REVIEW"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"
    PAUSED = "PAUSED"
    DONE = "DONE"


class Action(str, Enum):
    """Что Coordinator может сделать после оценки."""

    NONE = "NONE"
    LAUNCH_EXECUTOR = "LAUNCH_EXECUTOR"
    FAIL_CLOSED = "FAIL_CLOSED"


# Состояния, при которых запуск Executor запрещён явно.
NO_LAUNCH_STATES = frozenset(
    {
        CoordState.WAIT,
        CoordState.EXECUTOR_RUNNING,
        CoordState.ARCHITECT_REVIEW,
        CoordState.HUMAN_REQUIRED,
        CoordState.PAUSED,
        CoordState.DONE,
    }
)


@dataclass(frozen=True)
class BridgePrompt:
    """Разобранный next-prompt.md."""

    # Есть ли YAML front matter с coord_version.
    has_metadata: bool
    # Распознанное состояние (или None при fail-closed до нормализации).
    state: Optional[CoordState]
    # Идентификатор промпта из метаданных (может отсутствовать у legacy).
    prompt_id: Optional[str]
    # Целевой репозиторий / ветка / worktree / base SHA из метаданных.
    target_repo: Optional[str]
    target_branch: Optional[str]
    target_worktree: Optional[str]
    base_sha: Optional[str]
    # Политика hosted CI из метаданных (например forbidden).
    hosted_ci: Optional[str]
    # Жёсткий лимит запусков Executor на одну оценку.
    max_executor_runs: int
    # Полный текст файла (включая front matter), без переинтерпретации.
    raw_text: str
    # Тело промпта после front matter (для Executor).
    body: str
    # Сырые поля front matter (для отладки / отчёта).
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    # Причина fail-closed при разборе (если есть).
    parse_error: Optional[str] = None


@dataclass(frozen=True)
class SafetyReport:
    """Результат проверок безопасности перед launch."""

    ok: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Decision:
    """Итог одной оценки Coordinator."""

    action: Action
    state: Optional[CoordState]
    reason: str
    would_launch: bool
    mutations: tuple[str, ...] = ()
    safety: Optional[SafetyReport] = None


@dataclass(frozen=True)
class RunResult:
    """Результат одного вызова Coordinator (--once)."""

    mode: str
    decision: Decision
    executor_launched: bool
    executor_exit_code: Optional[int]
    messages: tuple[str, ...]
