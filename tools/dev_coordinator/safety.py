"""Проверки worktree / git перед запуском Executor."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from tools.dev_coordinator.models import BridgePrompt, SafetyReport


# Тип для подмены git-команд в unit-тестах.
GitRunner = Callable[[Sequence[str], Path], tuple[int, str, str]]


def _default_git_runner(args: Sequence[str], cwd: Path) -> tuple[int, str, str]:
    """Запуск git в указанном каталоге."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


@dataclass
class WorktreeSnapshot:
    """Снимок состояния worktree для safety-проверок."""

    path: Path
    branch: Optional[str]
    head_sha: Optional[str]
    is_dirty: bool
    status_short: str


def read_worktree_snapshot(
    worktree: Path,
    git_runner: GitRunner = _default_git_runner,
) -> WorktreeSnapshot:
    """Прочитать branch/HEAD/dirty без мутаций."""
    code_b, out_b, _ = git_runner(["branch", "--show-current"], worktree)
    branch = out_b.strip() if code_b == 0 else None

    code_h, out_h, _ = git_runner(["rev-parse", "HEAD"], worktree)
    head = out_h.strip() if code_h == 0 else None

    code_s, out_s, _ = git_runner(["status", "--porcelain"], worktree)
    status = out_s if code_s == 0 else "STATUS_UNAVAILABLE"
    dirty = bool(status.strip()) if code_s == 0 else True

    return WorktreeSnapshot(
        path=worktree,
        branch=branch,
        head_sha=head,
        is_dirty=dirty,
        status_short=status,
    )


def check_launch_safety(
    prompt: BridgePrompt,
    *,
    primary_repo: Path,
    executor_worktree: Path,
    expected_remote_sha: Optional[str] = None,
    executor_lock_held: bool = False,
    git_runner: GitRunner = _default_git_runner,
    allow_dirty: bool = False,
) -> SafetyReport:
    """Fail-closed проверки перед launch.

    Не делает stash/reset/clean. При любой неопределённости — ok=False.
    """
    reasons: list[str] = []

    # Нельзя молча переключать primary checkout.
    primary = primary_repo.resolve()
    target_wt = executor_worktree.resolve()
    if primary == target_wt:
        # Запуск в primary разрешён только если явно объявлен тот же путь
        # и ветка совпадает — но всё равно требуем объявленный target_worktree.
        if not prompt.target_worktree:
            reasons.append(
                "refusing to launch in primary checkout without declared target_worktree"
            )

    if prompt.target_worktree:
        declared = Path(prompt.target_worktree).expanduser().resolve()
        if declared != target_wt:
            reasons.append(
                f"target_worktree mismatch: declared={declared} actual={target_wt}"
            )
    else:
        # Без объявленного worktree — HUMAN_REQUIRED (fail closed для launch).
        reasons.append("missing declared target_worktree in metadata")

    snap = read_worktree_snapshot(target_wt, git_runner=git_runner)

    if prompt.target_branch:
        if snap.branch != prompt.target_branch:
            reasons.append(
                f"branch mismatch: declared={prompt.target_branch!r} actual={snap.branch!r}"
            )
    else:
        reasons.append("missing declared target_branch in metadata")

    if prompt.base_sha:
        if not snap.head_sha:
            reasons.append("unable to read HEAD for base_sha check")
        elif snap.head_sha != prompt.base_sha and (
            expected_remote_sha is None or snap.head_sha != expected_remote_sha
        ):
            # Требуем точное совпадение HEAD с base_sha (консервативно).
            if snap.head_sha != prompt.base_sha:
                reasons.append(
                    f"base SHA mismatch: declared={prompt.base_sha} head={snap.head_sha}"
                )
    else:
        reasons.append("missing declared base_sha in metadata")

    if snap.is_dirty and not allow_dirty:
        reasons.append("dirty/unsafe worktree: refusing to launch")

    if executor_lock_held:
        reasons.append("another Executor appears active (lock held)")

    # Политика hosted CI: Coordinator не создаёт PR / не диспатчит Actions.
    if prompt.hosted_ci and prompt.hosted_ci.lower() not in (
        "forbidden",
        "read_only",
        "informational",
    ):
        reasons.append(f"unsupported hosted_ci policy: {prompt.hosted_ci!r}")

    if prompt.max_executor_runs != 1:
        reasons.append(
            f"max_executor_runs={prompt.max_executor_runs} not allowed in v0.1 (must be 1)"
        )

    return SafetyReport(ok=not reasons, reasons=tuple(reasons))
