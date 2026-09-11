"""Явно объявленные transient tool artifacts (v0.2.1).

Не «игнорировать» untracked файлы. Контракт:
declared + absent before + untracked after + regular file
→ record evidence → unlink exact → re-verify status.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tools.dev_coordinator.gitutil import GitRunner, default_git_runner
from tools.dev_coordinator.models import FinalStatus
from tools.dev_coordinator.publication import parse_porcelain_paths

# Запрещённые символы glob / absolute / traversal.
_GLOB_CHARS_RE = re.compile(r"[*?\[\]]")


@dataclass(frozen=True)
class TransientBaseline:
    path: str
    exists_before: bool
    tracked_before: bool
    status_before: str


@dataclass(frozen=True)
class TransientCleanupResult:
    ok: bool
    reason: str
    final_status: FinalStatus
    declared: tuple[str, ...]
    observed: tuple[str, ...]
    cleaned: tuple[str, ...]
    cleanup_verified: bool
    sha256_by_path: dict[str, str]
    remaining_unexpected: tuple[str, ...] = ()


def validate_transient_path_syntax(path: str) -> Optional[str]:
    """Вернуть сообщение об ошибке или None если путь синтаксически ок."""
    if not path or not path.strip():
        return "empty transient path"
    p = path.strip()
    if p != path:
        # Уже strip на уровне списка; здесь строгая форма.
        pass
    if p.startswith("/") or (len(p) > 1 and p[1] == ":"):
        return f"absolute transient path forbidden: {path!r}"
    if ".." in p.split("/"):
        return f"parent traversal forbidden in transient path: {path!r}"
    if p.endswith("/") or p.endswith("\\"):
        return f"directory transient path unsupported: {path!r}"
    if "//" in p or p.startswith("./"):
        return f"empty/relative-dot components forbidden: {path!r}"
    parts = p.split("/")
    if any(part == "" for part in parts):
        return f"empty path component: {path!r}"
    if _GLOB_CHARS_RE.search(p):
        return f"glob patterns forbidden in transient path: {path!r}"
    return None


def validate_transient_paths(
    transient: tuple[str, ...],
    *,
    allowed: tuple[str, ...],
    required: tuple[str, ...],
) -> Optional[str]:
    """Валидация списка transient_paths. None = ok."""
    seen: set[str] = set()
    for path in transient:
        err = validate_transient_path_syntax(path)
        if err:
            return err
        if path in seen:
            return f"duplicate transient path: {path!r}"
        seen.add(path)
        if path in allowed:
            return f"transient_paths overlaps allowed_paths: {path}"
        if path in required:
            return f"transient_paths overlaps required_paths: {path}"
    return None


def is_path_tracked(
    worktree: Path,
    rel_path: str,
    git_runner: GitRunner = default_git_runner,
) -> bool:
    """True если путь tracked (`git ls-files --error-unmatch`)."""
    code, _out, _err = git_runner(
        ["ls-files", "--error-unmatch", "--", rel_path],
        worktree,
    )
    return code == 0


def porcelain_status_for_path(porcelain: str, rel_path: str) -> str:
    """Вернуть XY-статус строки для exact path или ''."""
    for raw in porcelain.splitlines():
        if not raw.strip():
            continue
        line = raw[3:] if len(raw) > 3 else raw
        if " -> " in line:
            line = line.split(" -> ", 1)[1]
        path = line.strip().strip('"')
        if path == rel_path:
            return raw[:2] if len(raw) >= 2 else "??"
    return ""


def snapshot_transients(
    paths: tuple[str, ...],
    *,
    executor_worktree: Path,
    git_runner: GitRunner = default_git_runner,
) -> tuple[tuple[TransientBaseline, ...], Optional[str]]:
    """Снимок до Executor. Если любой путь exists/tracked — ошибка."""
    wt = executor_worktree.resolve()
    code, porcelain, err = git_runner(["status", "--porcelain"], wt)
    if code != 0:
        return (), f"git status failed before launch: {err.strip()}"

    baselines: list[TransientBaseline] = []
    for rel in paths:
        abs_path = wt / rel
        exists = abs_path.exists()
        tracked = is_path_tracked(wt, rel, git_runner=git_runner)
        status = porcelain_status_for_path(porcelain, rel)
        baselines.append(
            TransientBaseline(
                path=rel,
                exists_before=exists,
                tracked_before=tracked,
                status_before=status,
            )
        )
        if exists or tracked:
            return (
                tuple(baselines),
                (
                    f"transient path not clean before launch: {rel} "
                    f"(exists={exists}, tracked={tracked}, status={status!r})"
                ),
            )
        # Директория до запуска тоже запрещена (не должно существовать).
        if abs_path.is_dir():
            return (
                tuple(baselines),
                f"transient path is a directory before launch: {rel}",
            )
    return tuple(baselines), None


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def classify_and_cleanup_transients(
    *,
    prompt_allowed: tuple[str, ...],
    prompt_transient: tuple[str, ...],
    baselines: tuple[TransientBaseline, ...],
    executor_worktree: Path,
    git_runner: GitRunner = default_git_runner,
) -> TransientCleanupResult:
    """После Executor: классификация + controlled cleanup + re-status."""
    wt = executor_worktree.resolve()
    declared = prompt_transient
    baseline_by_path = {b.path: b for b in baselines}

    code, porcelain, err = git_runner(["status", "--porcelain"], wt)
    if code != 0:
        return TransientCleanupResult(
            ok=False,
            reason=f"git status failed after executor: {err.strip()}",
            final_status=FinalStatus.POSTCONDITION_FAILED,
            declared=declared,
            observed=(),
            cleaned=(),
            cleanup_verified=False,
            sha256_by_path={},
        )

    changed = parse_porcelain_paths(porcelain)
    allowed = set(prompt_allowed)
    transient_set = set(declared)

    observed: list[str] = []
    unexpected: list[str] = []
    for path in changed:
        if path in allowed:
            continue
        if path in transient_set:
            observed.append(path)
            continue
        unexpected.append(path)

    if unexpected:
        return TransientCleanupResult(
            ok=False,
            reason=(
                "POSTCONDITION_FAILED: undeclared unexpected paths: "
                + ", ".join(unexpected)
            ),
            final_status=FinalStatus.POSTCONDITION_FAILED,
            declared=declared,
            observed=tuple(observed),
            cleaned=(),
            cleanup_verified=False,
            sha256_by_path={},
            remaining_unexpected=tuple(unexpected),
        )

    # Проверить каждый observed transient по строгому контракту.
    sha_map: dict[str, str] = {}
    cleaned: list[str] = []
    for path in observed:
        base = baseline_by_path.get(path)
        if base is None:
            return TransientCleanupResult(
                ok=False,
                reason=f"missing baseline for transient path: {path}",
                final_status=FinalStatus.POSTCONDITION_FAILED,
                declared=declared,
                observed=tuple(observed),
                cleaned=(),
                cleanup_verified=False,
                sha256_by_path={},
            )
        if base.exists_before or base.tracked_before:
            return TransientCleanupResult(
                ok=False,
                reason=(
                    f"transient path existed/tracked before launch; "
                    f"no cleanup: {path}"
                ),
                final_status=FinalStatus.POSTCONDITION_FAILED,
                declared=declared,
                observed=tuple(observed),
                cleaned=(),
                cleanup_verified=False,
                sha256_by_path={},
            )

        status = porcelain_status_for_path(porcelain, path)
        # Должен быть untracked: ?? 
        if not status.startswith("?"):
            return TransientCleanupResult(
                ok=False,
                reason=(
                    f"transient path is not untracked after executor "
                    f"(status={status!r}): {path}"
                ),
                final_status=FinalStatus.POSTCONDITION_FAILED,
                declared=declared,
                observed=tuple(observed),
                cleaned=(),
                cleanup_verified=False,
                sha256_by_path={},
            )

        abs_path = wt / path
        if not abs_path.is_file() or abs_path.is_symlink():
            return TransientCleanupResult(
                ok=False,
                reason=(
                    f"transient path is not a regular file after executor: {path}"
                ),
                final_status=FinalStatus.POSTCONDITION_FAILED,
                declared=declared,
                observed=tuple(observed),
                cleaned=(),
                cleanup_verified=False,
                sha256_by_path={},
            )

        # Evidence до удаления.
        try:
            sha_map[path] = _file_sha256(abs_path)
        except OSError as exc:
            return TransientCleanupResult(
                ok=False,
                reason=f"unable to hash transient file {path}: {exc}",
                final_status=FinalStatus.POSTCONDITION_FAILED,
                declared=declared,
                observed=tuple(observed),
                cleaned=(),
                cleanup_verified=False,
                sha256_by_path={},
            )

        try:
            abs_path.unlink()
        except OSError as exc:
            return TransientCleanupResult(
                ok=False,
                reason=f"transient cleanup failed for {path}: {exc}",
                final_status=FinalStatus.POSTCONDITION_FAILED,
                declared=declared,
                observed=tuple(observed),
                cleaned=tuple(cleaned),
                cleanup_verified=False,
                sha256_by_path=sha_map,
            )
        cleaned.append(path)

    # Повторный status: transient должны исчезнуть; unexpected — нет.
    code2, porcelain2, err2 = git_runner(["status", "--porcelain"], wt)
    if code2 != 0:
        return TransientCleanupResult(
            ok=False,
            reason=f"git status failed after cleanup: {err2.strip()}",
            final_status=FinalStatus.POSTCONDITION_FAILED,
            declared=declared,
            observed=tuple(observed),
            cleaned=tuple(cleaned),
            cleanup_verified=False,
            sha256_by_path=sha_map,
        )

    after = parse_porcelain_paths(porcelain2)
    leftover_transient = [p for p in cleaned if p in after]
    leftover_unexpected = [p for p in after if p not in allowed]
    if leftover_transient or leftover_unexpected:
        return TransientCleanupResult(
            ok=False,
            reason=(
                "POSTCONDITION_FAILED: after cleanup still dirty: "
                + ", ".join(leftover_transient + leftover_unexpected)
            ),
            final_status=FinalStatus.POSTCONDITION_FAILED,
            declared=declared,
            observed=tuple(observed),
            cleaned=tuple(cleaned),
            cleanup_verified=False,
            sha256_by_path=sha_map,
            remaining_unexpected=tuple(leftover_unexpected),
        )

    return TransientCleanupResult(
        ok=True,
        reason="transient cleanup verified",
        final_status=FinalStatus.WORK_PACKAGE_SUCCESS,
        declared=declared,
        observed=tuple(observed),
        cleaned=tuple(cleaned),
        cleanup_verified=True,
        sha256_by_path=sha_map,
    )
