"""Безопасная подготовка bridge/executor worktrees под managed root."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tools.dev_coordinator.gitutil import (
    GitRunner,
    default_git_runner,
    read_origin_repo,
    read_remote_branch_tip,
)
from tools.dev_coordinator.safety import read_worktree_snapshot

# Запрещённые целевые ветки executor.
_FORBIDDEN_TARGET_BRANCHES = frozenset({"main", "master"})

# Небезопасные символы в имени каталога worktree.
_UNSAFE_PATH_CHARS = re.compile(r"[^\w.\-]+")


@dataclass(frozen=True)
class WorktreePrepareResult:
    """Результат подготовки worktree."""

    ok: bool
    path: Optional[Path]
    reason: str
    created: bool = False


def is_path_contained(child: Path, root: Path) -> bool:
    """Проверить каноническое вложение child под root (fail closed)."""
    try:
        child_resolved = child.expanduser().resolve(strict=False)
        root_resolved = root.expanduser().resolve(strict=False)
    except OSError:
        return False
    try:
        child_resolved.relative_to(root_resolved)
        return True
    except ValueError:
        return False


def repo_short_name(canonical_repo: str) -> str:
    """OWNER/REPO → REPO (последний сегмент)."""
    return canonical_repo.rsplit("/", 1)[-1]


def sanitize_branch_for_path(branch: str) -> str:
    """Преобразовать имя ветки в безопасный сегмент пути."""
    text = branch.strip().replace("/", "-")
    text = _UNSAFE_PATH_CHARS.sub("-", text)
    text = text.strip("-")
    return text or "branch"


def derive_bridge_worktree_path(
    managed_root: Path,
    canonical_repo: str,
    bridge_branch: str,
) -> Path:
    """Путь bridge-worktree под managed root (детерминированный)."""
    short = repo_short_name(canonical_repo)
    safe_branch = sanitize_branch_for_path(bridge_branch)
    return (managed_root / "bridge" / short / safe_branch).resolve()


def derive_executor_worktree_path(
    managed_root: Path,
    canonical_repo: str,
    target_branch: str,
) -> Path:
    """Путь executor-worktree под managed root (совпадает с принятой схемой)."""
    short = repo_short_name(canonical_repo)
    safe_branch = sanitize_branch_for_path(target_branch)
    return (managed_root / short / safe_branch).resolve()


def _list_worktree_paths(
    repo_clone: Path,
    git_runner: GitRunner,
) -> list[Path]:
    """Список путей всех зарегистрированных worktree для репозитория."""
    code, out, _ = git_runner(["worktree", "list", "--porcelain"], repo_clone)
    if code != 0:
        return []
    paths: list[Path] = []
    for line in out.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line.split(" ", 1)[1].strip()).resolve())
    return paths


def _branch_checked_out_outside_managed(
    repo_clone: Path,
    branch: str,
    managed_root: Path,
    git_runner: GitRunner,
) -> Optional[Path]:
    """Найти checkout ветки вне managed root (коллизия → fail closed)."""
    for wt_path in _list_worktree_paths(repo_clone, git_runner):
        # Пропускаем устаревшие регистрации: git не должен вызываться с cwd
        # в каталоге, которого уже нет (иначе FileNotFoundError рвёт весь scan).
        if not wt_path.is_dir():
            continue
        snap = read_worktree_snapshot(wt_path, git_runner=git_runner)
        if snap.branch == branch and not is_path_contained(wt_path, managed_root):
            return wt_path
    return None


def _remote_branch_exists(
    repo_clone: Path,
    branch: str,
    expected_sha: str,
    git_runner: GitRunner,
) -> tuple[bool, str]:
    """Проверить существование remote ref и совпадение SHA."""
    tip = read_remote_branch_tip(repo_clone, branch, git_runner=git_runner)
    if tip is None:
        return False, f"remote branch missing: origin/{branch}"
    if tip != expected_sha:
        return (
            False,
            f"remote branch SHA mismatch: expected={expected_sha} actual={tip}",
        )
    return True, "ok"


def _fast_forward_worktree(
    worktree: Path,
    *,
    expected_repo: str,
    expected_branch: str,
    target_sha: str,
    git_runner: GitRunner,
) -> tuple[bool, str]:
    """Безопасно продвинуть существующий clean worktree до target_sha (только ff-only)."""
    snap = read_worktree_snapshot(worktree, git_runner=git_runner)
    if snap.is_dirty:
        return False, f"worktree is dirty: {worktree}"
    if snap.branch != expected_branch:
        return (
            False,
            f"branch mismatch at {worktree}: expected={expected_branch!r} "
            f"actual={snap.branch!r}",
        )
    if snap.head_sha == target_sha:
        return True, "already at target sha"

    canonical, _ = read_origin_repo(worktree, git_runner=git_runner)
    if canonical != expected_repo:
        return (
            False,
            f"origin repo mismatch at {worktree}: expected={expected_repo} "
            f"actual={canonical}",
        )

    code, out, err = git_runner(["merge", "--ff-only", target_sha], worktree)
    if code != 0:
        return False, f"fast-forward merge failed: {err or out}".strip()
    return True, "fast-forwarded"


def _worktree_matches(
    worktree: Path,
    *,
    expected_repo: str,
    expected_branch: str,
    expected_sha: str,
    git_runner: GitRunner,
) -> tuple[bool, str]:
    """Точное совпадение repo/branch/SHA/clean для reuse."""
    if not worktree.is_dir():
        return False, f"worktree path does not exist: {worktree}"

    code, out, _ = git_runner(["rev-parse", "--is-inside-work-tree"], worktree)
    if code != 0 or out.strip() != "true":
        return False, f"path is not a git worktree: {worktree}"

    snap = read_worktree_snapshot(worktree, git_runner=git_runner)
    if snap.is_dirty:
        return False, f"worktree is dirty: {worktree}"
    if snap.branch != expected_branch:
        return (
            False,
            f"branch mismatch at {worktree}: expected={expected_branch!r} "
            f"actual={snap.branch!r}",
        )
    if snap.head_sha != expected_sha:
        return (
            False,
            f"HEAD SHA mismatch at {worktree}: expected={expected_sha} "
            f"actual={snap.head_sha}",
        )

    canonical, _ = read_origin_repo(worktree, git_runner=git_runner)
    if canonical != expected_repo:
        return (
            False,
            f"origin repo mismatch at {worktree}: expected={expected_repo} "
            f"actual={canonical}",
        )
    return True, "ok"


def _create_worktree(
    repo_clone: Path,
    worktree_path: Path,
    branch: str,
    remote_sha: str,
    git_runner: GitRunner,
) -> tuple[bool, str]:
    """Создать новый tracked worktree (без force/reset/clean)."""
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    # Проверяем, существует ли локальная ветка.
    code_lb, out_lb, _ = git_runner(
        ["show-ref", "--verify", f"refs/heads/{branch}"],
        repo_clone,
    )
    local_exists = code_lb == 0

    if local_exists:
        argv = ["worktree", "add", str(worktree_path), branch]
    else:
        argv = [
            "worktree",
            "add",
            "--track",
            "-b",
            branch,
            str(worktree_path),
            f"origin/{branch}",
        ]

    code, out, err = git_runner(argv, repo_clone)
    if code != 0:
        return False, f"git worktree add failed: {err or out}".strip()

    ok, reason = _worktree_matches(
        worktree_path,
        expected_repo=_read_canonical_from_clone(repo_clone, git_runner) or "",
        expected_branch=branch,
        expected_sha=remote_sha,
        git_runner=git_runner,
    )
    if not ok:
        return False, f"new worktree verification failed: {reason}"
    return True, "created"


def _read_canonical_from_clone(
    repo_clone: Path,
    git_runner: GitRunner,
) -> Optional[str]:
    canonical, _ = read_origin_repo(repo_clone, git_runner=git_runner)
    return canonical


def prepare_bridge_worktree(
    *,
    repo_clone: Path,
    canonical_repo: str,
    bridge_branch: str,
    bridge_sha: str,
    managed_root: Path,
    git_runner: GitRunner = default_git_runner,
) -> WorktreePrepareResult:
    """Подготовить или безопасно переиспользовать bridge worktree."""
    if not bridge_branch.startswith("coord/bridge/"):
        return WorktreePrepareResult(
            ok=False,
            path=None,
            reason=f"bridge branch outside namespace: {bridge_branch!r}",
        )

    worktree_path = derive_bridge_worktree_path(
        managed_root, canonical_repo, bridge_branch
    )
    if not is_path_contained(worktree_path, managed_root):
        return WorktreePrepareResult(
            ok=False,
            path=None,
            reason=f"derived bridge path escapes managed root: {worktree_path}",
        )

    outside = _branch_checked_out_outside_managed(
        repo_clone, bridge_branch, managed_root, git_runner
    )
    if outside is not None:
        return WorktreePrepareResult(
            ok=False,
            path=None,
            reason=(
                f"branch {bridge_branch!r} checked out outside managed root: {outside}"
            ),
        )

    remote_ok, remote_reason = _remote_branch_exists(
        repo_clone, bridge_branch, bridge_sha, git_runner
    )
    if not remote_ok:
        return WorktreePrepareResult(ok=False, path=None, reason=remote_reason)

    if worktree_path.is_dir():
        ok, reason = _worktree_matches(
            worktree_path,
            expected_repo=canonical_repo,
            expected_branch=bridge_branch,
            expected_sha=bridge_sha,
            git_runner=git_runner,
        )
        if ok:
            return WorktreePrepareResult(
                ok=True,
                path=worktree_path,
                reason="reused existing bridge worktree",
                created=False,
            )

        snap = read_worktree_snapshot(worktree_path, git_runner=git_runner)
        canonical, _ = read_origin_repo(worktree_path, git_runner=git_runner)
        can_fast_forward = (
            not snap.is_dirty
            and snap.branch == bridge_branch
            and canonical == canonical_repo
            and snap.head_sha is not None
            and snap.head_sha != bridge_sha
        )
        if can_fast_forward:
            ff_ok, ff_reason = _fast_forward_worktree(
                worktree_path,
                expected_repo=canonical_repo,
                expected_branch=bridge_branch,
                target_sha=bridge_sha,
                git_runner=git_runner,
            )
            if ff_ok:
                ok, verify_reason = _worktree_matches(
                    worktree_path,
                    expected_repo=canonical_repo,
                    expected_branch=bridge_branch,
                    expected_sha=bridge_sha,
                    git_runner=git_runner,
                )
                if ok:
                    return WorktreePrepareResult(
                        ok=True,
                        path=worktree_path,
                        reason="advanced existing bridge worktree via fast-forward",
                        created=False,
                    )
                return WorktreePrepareResult(
                    ok=False,
                    path=worktree_path,
                    reason=f"post fast-forward verification failed: {verify_reason}",
                )
            return WorktreePrepareResult(
                ok=False,
                path=worktree_path,
                reason=ff_reason,
            )

        return WorktreePrepareResult(
            ok=False,
            path=worktree_path,
            reason=f"stale/inconsistent bridge worktree: {reason}",
        )

    created_ok, created_reason = _create_worktree(
        repo_clone,
        worktree_path,
        bridge_branch,
        bridge_sha,
        git_runner,
    )
    if not created_ok:
        return WorktreePrepareResult(
            ok=False,
            path=worktree_path,
            reason=created_reason,
        )
    return WorktreePrepareResult(
        ok=True,
        path=worktree_path,
        reason=created_reason,
        created=True,
    )


def prepare_executor_worktree(
    *,
    repo_clone: Path,
    canonical_repo: str,
    target_branch: str,
    base_sha: str,
    declared_worktree: Path,
    managed_root: Path,
    git_runner: GitRunner = default_git_runner,
) -> WorktreePrepareResult:
    """Подготовить или безопасно переиспользовать executor worktree."""
    if target_branch in _FORBIDDEN_TARGET_BRANCHES:
        return WorktreePrepareResult(
            ok=False,
            path=None,
            reason=f"forbidden target branch: {target_branch!r}",
        )

    declared_resolved = declared_worktree.expanduser().resolve()
    if not is_path_contained(declared_resolved, managed_root):
        return WorktreePrepareResult(
            ok=False,
            path=None,
            reason=(
                f"declared target_worktree outside managed root: {declared_resolved}"
            ),
        )

    expected_path = derive_executor_worktree_path(
        managed_root, canonical_repo, target_branch
    )
    if declared_resolved != expected_path:
        return WorktreePrepareResult(
            ok=False,
            path=None,
            reason=(
                f"declared target_worktree mismatch: declared={declared_resolved} "
                f"expected={expected_path}"
            ),
        )

    outside = _branch_checked_out_outside_managed(
        repo_clone, target_branch, managed_root, git_runner
    )
    if outside is not None:
        return WorktreePrepareResult(
            ok=False,
            path=None,
            reason=(
                f"branch {target_branch!r} checked out outside managed root: {outside}"
            ),
        )

    remote_ok, remote_reason = _remote_branch_exists(
        repo_clone, target_branch, base_sha, git_runner
    )
    if not remote_ok:
        return WorktreePrepareResult(ok=False, path=None, reason=remote_reason)

    if expected_path.is_dir():
        ok, reason = _worktree_matches(
            expected_path,
            expected_repo=canonical_repo,
            expected_branch=target_branch,
            expected_sha=base_sha,
            git_runner=git_runner,
        )
        if ok:
            return WorktreePrepareResult(
                ok=True,
                path=expected_path,
                reason="reused existing executor worktree",
                created=False,
            )
        return WorktreePrepareResult(
            ok=False,
            path=expected_path,
            reason=f"stale/inconsistent executor worktree: {reason}",
        )

    created_ok, created_reason = _create_worktree(
        repo_clone,
        expected_path,
        target_branch,
        base_sha,
        git_runner,
    )
    if not created_ok:
        return WorktreePrepareResult(
            ok=False,
            path=expected_path,
            reason=created_reason,
        )
    return WorktreePrepareResult(
        ok=True,
        path=expected_path,
        reason=created_reason,
        created=True,
    )


def validate_declared_executor_path(
    declared_worktree: str | Path,
    managed_root: Path,
    canonical_repo: str,
    target_branch: str,
) -> tuple[bool, str, Optional[Path]]:
    """Проверить declared target_worktree до создания worktree."""
    if target_branch in _FORBIDDEN_TARGET_BRANCHES:
        return False, f"forbidden target branch: {target_branch!r}", None

    try:
        declared = Path(declared_worktree).expanduser().resolve()
    except OSError as exc:
        return False, f"invalid target_worktree path: {exc}", None

    if not is_path_contained(declared, managed_root):
        return (
            False,
            f"target_worktree outside managed root: {declared}",
            declared,
        )

    expected = derive_executor_worktree_path(managed_root, canonical_repo, target_branch)
    if declared != expected:
        return (
            False,
            f"target_worktree path mismatch: declared={declared} expected={expected}",
            declared,
        )
    return True, "ok", declared
