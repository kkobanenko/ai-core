"""Модели состояния Coordinator v0.2."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class CoordState(str, Enum):
    """Разрешённые состояния."""

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


class FinalStatus(str, Enum):
    """Итоговый статус work package (не путать с exit code Executor)."""

    SHADOW_OK = "SHADOW_OK"
    WAIT_OK = "WAIT_OK"
    FAIL_CLOSED = "FAIL_CLOSED"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"
    EXECUTOR_PROCESS_EXITED_ZERO = "EXECUTOR_PROCESS_EXITED_ZERO"
    EXECUTOR_NONZERO = "EXECUTOR_NONZERO"
    POSTCONDITION_FAILED = "POSTCONDITION_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    PUBLICATION_FAILED = "PUBLICATION_FAILED"
    PUBLICATION_UNVERIFIED = "PUBLICATION_UNVERIFIED"
    WORK_PACKAGE_SUCCESS = "WORK_PACKAGE_SUCCESS"


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

    has_metadata: bool
    state: Optional[CoordState]
    prompt_id: Optional[str]
    target_repo: Optional[str]
    target_branch: Optional[str]
    target_worktree: Optional[str]
    base_sha: Optional[str]
    hosted_ci: Optional[str]
    max_executor_runs: int
    raw_text: str
    body: str
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    parse_error: Optional[str] = None
    # v0.2 publication contract (flat fields).
    allowed_paths: tuple[str, ...] = ()
    required_paths: tuple[str, ...] = ()
    publication_commit: bool = False
    publication_push: bool = False
    commit_message: Optional[str] = None


@dataclass(frozen=True)
class SafetyReport:
    ok: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Decision:
    action: Action
    state: Optional[CoordState]
    reason: str
    would_launch: bool
    mutations: tuple[str, ...] = ()
    safety: Optional[SafetyReport] = None


@dataclass(frozen=True)
class RunResult:
    """Результат одного вызова Coordinator (--once) — v0.2."""

    mode: str
    decision: Decision
    executor_launched: bool
    executor_exit_code: Optional[int]
    messages: tuple[str, ...]
    final_status: FinalStatus = FinalStatus.FAIL_CLOSED
    postconditions_ok: Optional[bool] = None
    unexpected_paths: tuple[str, ...] = ()
    required_paths_ok: Optional[bool] = None
    validation_ok: Optional[bool] = None
    commit_created: bool = False
    local_head: Optional[str] = None
    push_attempted: bool = False
    remote_head: Optional[str] = None
    publication_verified: bool = False
    elapsed_seconds: Optional[float] = None
    executor_stdout_tail: Optional[str] = None
    executor_stderr_tail: Optional[str] = None
    executor_log_path: Optional[str] = None
