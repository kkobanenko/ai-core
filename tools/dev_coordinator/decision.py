"""Детерминированное решение: запускать Executor или нет (v0.1.1)."""

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
    git_runner: Optional[GitRunner] = None,
    allow_dirty: bool = False,
    force_safety_check: bool = False,
    # Если True — safety уже проверен снаружи (bridge + executor); skip здесь.
    skip_executor_safety: bool = False,
) -> Decision:
    """Одна оценка состояния bridge (без claim/lock — это делает cli.run_once)."""
    if mode not in ("shadow", "launch"):
        return Decision(
            action=Action.FAIL_CLOSED,
            state=None,
            reason=f"unknown mode: {mode!r}",
            would_launch=False,
            mutations=(),
        )

    # v0.1.1: launch + allow-dirty запрещены (unattended live).
    if mode == "launch" and allow_dirty:
        return Decision(
            action=Action.FAIL_CLOSED,
            state=CoordState.HUMAN_REQUIRED,
            reason="launch + allow-dirty is forbidden in v0.1.1",
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

    if prompt.max_executor_runs != 1:
        return Decision(
            action=Action.FAIL_CLOSED,
            state=state,
            reason=(
                f"fail closed: max_executor_runs={prompt.max_executor_runs} "
                "(v0.1.1 enforces exactly 1)"
            ),
            would_launch=False,
            mutations=(),
        )

    need_safety = (
        not skip_executor_safety
        and (mode == "launch" or force_safety_check or prompt.has_metadata)
    )
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
            # Live path never passes allow_dirty=True into safety.
            allow_dirty=False,
            **kwargs,
        )
        if not safety.ok:
            return Decision(
                action=Action.NONE,
                state=CoordState.HUMAN_REQUIRED,
                reason="unsafe worktree/git state: " + "; ".join(safety.reasons),
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

    return Decision(
        action=Action.LAUNCH_EXECUTOR,
        state=state,
        reason="EXECUTOR_READY and safety checks passed: launch once",
        would_launch=True,
        mutations=("launch_executor",),
        safety=safety,
    )
