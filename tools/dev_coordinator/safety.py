"""Проверки worktree / git / bridge source перед запуском Executor (v0.1.1)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tools.dev_coordinator.gitutil import (
    GitRunner,
    default_git_runner,
    read_origin_repo,
    read_remote_branch_tip,
)
from tools.dev_coordinator.models import BridgePrompt, CoordState, SafetyReport

# Обратная совместимость имени для тестов/импортов.
_default_git_runner = default_git_runner


@dataclass
class WorktreeSnapshot:
    path: Path
    branch: Optional[str]
    head_sha: Optional[str]
    is_dirty: bool
    status_short: str


def read_worktree_snapshot(
    worktree: Path,
    git_runner: GitRunner = default_git_runner,
) -> WorktreeSnapshot:
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


def verify_bridge_source(
    *,
    bridge_worktree: Path,
    bridge_prompt_path: Path,
    expected_repo: Optional[str],
    mode: str,
    git_runner: GitRunner = default_git_runner,
    require_remote_match: bool = True,
) -> SafetyReport:
    """Проверить, что bridge-prompt принадлежит declared bridge worktree/repo."""
    reasons: list[str] = []
    bw = bridge_worktree.resolve()
    bp = bridge_prompt_path.resolve()

    try:
        bp.relative_to(bw)
    except ValueError:
        reasons.append(
            f"bridge-prompt not inside bridge-worktree: prompt={bp} worktree={bw}"
        )
        return SafetyReport(ok=False, reasons=tuple(reasons))

    if not bp.is_file():
        reasons.append(f"bridge-prompt is not a file: {bp}")

    code, out, _ = git_runner(["rev-parse", "--is-inside-work-tree"], bw)
    if code != 0 or out.strip() != "true":
        reasons.append(f"bridge-worktree is not a git worktree: {bw}")
        return SafetyReport(ok=False, reasons=tuple(reasons))

    snap = read_worktree_snapshot(bw, git_runner=git_runner)
    if not snap.branch:
        reasons.append("bridge branch is not determinable")
    if not snap.head_sha:
        reasons.append("bridge local HEAD is not determinable")

    canonical, raw_url = read_origin_repo(bw, git_runner=git_runner)
    if not canonical:
        reasons.append(f"unable to canonicalize bridge origin URL: {raw_url!r}")
    elif expected_repo and canonical != expected_repo:
        reasons.append(
            f"bridge repo mismatch: origin={canonical} expected={expected_repo}"
        )

    if snap.branch and snap.head_sha and require_remote_match:
        remote_tip = read_remote_branch_tip(bw, snap.branch, git_runner=git_runner)
        if remote_tip is None:
            reasons.append(
                "unable to read remote bridge tip via git ls-remote "
                f"(branch={snap.branch!r})"
            )
        elif remote_tip != snap.head_sha:
            reasons.append(
                f"bridge local HEAD drift vs remote: local={snap.head_sha} "
                f"remote={remote_tip}"
            )
    elif snap.branch and snap.head_sha and mode == "shadow" and not require_remote_match:
        remote_tip = read_remote_branch_tip(bw, snap.branch, git_runner=git_runner)
        if remote_tip is not None and remote_tip != snap.head_sha:
            reasons.append(
                f"shadow note: bridge local HEAD != remote tip "
                f"({snap.head_sha} vs {remote_tip})"
            )

    return SafetyReport(ok=not reasons, reasons=tuple(reasons))


def check_launch_safety(
    prompt: BridgePrompt,
    *,
    primary_repo: Path,
    executor_worktree: Path,
    expected_remote_sha: Optional[str] = None,
    git_runner: GitRunner = default_git_runner,
    allow_dirty: bool = False,
) -> SafetyReport:
    """Fail-closed проверки executor worktree перед launch."""
    reasons: list[str] = []

    if prompt.state != CoordState.EXECUTOR_READY:
        reasons.append(
            f"check_launch_safety only for EXECUTOR_READY, got {prompt.state}"
        )
        return SafetyReport(ok=False, reasons=tuple(reasons))

    target_wt = executor_worktree.resolve()

    if not prompt.target_worktree:
        reasons.append("missing declared target_worktree in metadata")
    else:
        declared = Path(prompt.target_worktree).expanduser().resolve()
        if declared != target_wt:
            reasons.append(
                f"target_worktree mismatch: declared={declared} actual={target_wt}"
            )

    snap = read_worktree_snapshot(target_wt, git_runner=git_runner)

    if not prompt.target_branch:
        reasons.append("missing declared target_branch in metadata")
    elif snap.branch != prompt.target_branch:
        reasons.append(
            f"branch mismatch: declared={prompt.target_branch!r} actual={snap.branch!r}"
        )

    if not prompt.base_sha:
        reasons.append("missing declared base_sha in metadata")
    elif not snap.head_sha:
        reasons.append("unable to read HEAD for base_sha check")
    elif snap.head_sha != prompt.base_sha:
        reasons.append(
            f"base SHA mismatch: declared={prompt.base_sha} head={snap.head_sha}"
        )

    if not prompt.target_repo:
        reasons.append("missing declared target_repo in metadata")
    else:
        canonical, raw_url = read_origin_repo(target_wt, git_runner=git_runner)
        if not canonical:
            reasons.append(f"unable to canonicalize executor origin URL: {raw_url!r}")
        elif canonical != prompt.target_repo:
            reasons.append(
                f"target_repo mismatch: declared={prompt.target_repo} origin={canonical}"
            )

    if snap.is_dirty:
        reasons.append("dirty/unsafe worktree: refusing to launch")
    if allow_dirty:
        reasons.append("allow_dirty is not permitted for live launch safety path")

    if prompt.hosted_ci and prompt.hosted_ci.lower() not in (
        "forbidden",
        "read_only",
        "informational",
    ):
        reasons.append(f"unsupported hosted_ci policy: {prompt.hosted_ci!r}")

    if prompt.max_executor_runs != 1:
        reasons.append(
            f"max_executor_runs={prompt.max_executor_runs} not allowed in v0.1.1 (must be 1)"
        )

    _ = expected_remote_sha
    _ = primary_repo

    return SafetyReport(ok=not reasons, reasons=tuple(reasons))
