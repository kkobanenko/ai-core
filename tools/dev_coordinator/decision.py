"""Детерминированное решение: запускать Executor или нет."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from tools.dev_coordinator.models import (
    NO_LAUNCH_STATES,
    Action,
    BridgePrompt,
    CoordState,
    Decision,
    SafetyReport,
)
from tools.dev_coordinator.safety import GitRunner, check_launch_safety


def decide(
    prompt: BridgePrompt,
    *,
    mode: str,
    primary_repo: Path,
    executor_worktree: Path,
    expected_remote_sha: Optional[str] = None,
    executor_lock_held: bool = False,
    git_runner: Optional[GitRunner] = None,
    allow_dirty: bool = False,
    force_safety_check: bool = False,
) -> Decision:
    """Одна оценка состояния bridge.

    mode:
      - shadow: никогда не мутирует; would_launch отражает гипотетический launch;
      - launch: возвращает LAUNCH_EXECUTOR только при полном прохождении проверок.
    """
    if mode not in ("shadow", "launch"):
        return Decision(
            action=Action.FAIL_CLOSED,
            state=None,
            reason=f"unknown mode: {mode!r}",
            would_launch=False,
            mutations=(),
        )

    if prompt.parse_error:
        return Decision(
            action=Action.FAIL_CLOSED,
            state=None,
            reason=f"fail closed: {prompt.parse_error}",
            would_launch=False,
            mutations=(),
        )

    if prompt.state is None:
        return Decision(
            action=Action.FAIL_CLOSED,
            state=None,
            reason="fail closed: missing state",
            would_launch=False,
            mutations=(),
        )

    state = prompt.state

    # Явные no-launch состояния (включая legacy WAIT).
    if state in NO_LAUNCH_STATES:
        return Decision(
            action=Action.NONE,
            state=state,
            reason=f"state={state.value}: no executor launch",
            would_launch=False,
            mutations=(),
        )

    if state != CoordState.EXECUTOR_READY:
        return Decision(
            action=Action.FAIL_CLOSED,
            state=state,
            reason=f"fail closed: unexpected state {state.value}",
            would_launch=False,
            mutations=(),
        )

    # EXECUTOR_READY: проверяем max_executor_runs и safety.
    if prompt.max_executor_runs != 1:
        return Decision(
            action=Action.FAIL_CLOSED,
            state=state,
            reason=(
                f"fail closed: max_executor_runs={prompt.max_executor_runs} "
                "(v0.1 enforces exactly 1)"
            ),
            would_launch=False,
            mutations=(),
        )

    # В shadow можно пропускать тяжёлые git-проверки, если не запрошено,
    # но для честного «would launch» всё равно считаем safety при наличии
    # метаданных worktree/branch/base.
    need_safety = mode == "launch" or force_safety_check or prompt.has_metadata
    safety: Optional[SafetyReport] = None
    if need_safety:
        kwargs = {}
        if git_runner is not None:
            kwargs["git_runner"] = git_runner
        safety = check_launch_safety(
            prompt,
            primary_repo=primary_repo,
            executor_worktree=executor_worktree,
            expected_remote_sha=expected_remote_sha,
            executor_lock_held=executor_lock_held,
            allow_dirty=allow_dirty,
            **kwargs,
        )
        if not safety.ok:
            return Decision(
                action=Action.NONE,
                state=CoordState.HUMAN_REQUIRED,
                reason="unsafe worktree/git state: "
                + "; ".join(safety.reasons),
                would_launch=False,
                mutations=(),
                safety=safety,
            )

    if mode == "shadow":
        return Decision(
            action=Action.NONE,
            state=state,
            reason="shadow mode: would launch executor once (no mutations)",
            would_launch=True,
            mutations=(),
            safety=safety,
        )

    # mode == launch
    return Decision(
        action=Action.LAUNCH_EXECUTOR,
        state=state,
        reason="EXECUTOR_READY and safety checks passed: launch once",
        would_launch=True,
        mutations=("launch_executor",),
        safety=safety,
    )
