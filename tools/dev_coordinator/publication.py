"""Детерминированная postcondition-проверка и publication (v0.2).

Coordinator владеет: validate → exact-path commit → push → remote verify.
Executor не обязан commit/push.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from tools.dev_coordinator.gitutil import GitRunner, default_git_runner
from tools.dev_coordinator.models import BridgePrompt, FinalStatus


FORBIDDEN_ADD_ARGS = frozenset({".", "-A", "--all", "-u", "--update"})


@dataclass(frozen=True)
class PostconditionResult:
    ok: bool
    unexpected_paths: tuple[str, ...]
    required_paths_ok: bool
    validation_ok: bool
    changed_paths: tuple[str, ...]
    reason: str
    final_status: FinalStatus


@dataclass(frozen=True)
class PublicationResult:
    commit_created: bool
    local_head: Optional[str]
    push_attempted: bool
    remote_head: Optional[str]
    publication_verified: bool
    final_status: FinalStatus
    reason: str
    staged_paths: tuple[str, ...] = ()
    git_commands: tuple[tuple[str, ...], ...] = ()


def parse_porcelain_paths(porcelain: str) -> tuple[str, ...]:
    """Извлечь пути из `git status --porcelain` (без доверия Executor)."""
    paths: list[str] = []
    for raw in porcelain.splitlines():
        if not raw.strip():
            continue
        # Форматы: XY PATH | XY ORIG -> PATH | ?? PATH
        line = raw[3:] if len(raw) > 3 else raw
        if " -> " in line:
            line = line.split(" -> ", 1)[1]
        path = line.strip().strip('"')
        if path:
            paths.append(path)
    # Уникальные, стабильный порядок.
    return tuple(sorted(set(paths)))


def evaluate_postconditions(
    prompt: BridgePrompt,
    *,
    executor_worktree: Path,
    git_runner: GitRunner = default_git_runner,
) -> PostconditionResult:
    """Фактический worktree state — authoritative."""
    wt = executor_worktree.resolve()
    allowed = set(prompt.allowed_paths)
    required = list(prompt.required_paths)

    code, out, err = git_runner(["status", "--porcelain"], wt)
    if code != 0:
        return PostconditionResult(
            ok=False,
            unexpected_paths=(),
            required_paths_ok=False,
            validation_ok=False,
            changed_paths=(),
            reason=f"git status failed: {err.strip() or out.strip()}",
            final_status=FinalStatus.POSTCONDITION_FAILED,
        )

    changed = parse_porcelain_paths(out)
    unexpected = tuple(p for p in changed if p not in allowed)

    missing_required = [
        p for p in required if not (wt / p).is_file()
    ]
    required_ok = not missing_required

    # git diff --check (staged+unstaged working tree)
    vcode, vout, verr = git_runner(["diff", "--check"], wt)
    # Также unstaged for untracked? diff --check only tracks tracked diffs.
    # For new files, --check on empty may be 0; that's OK. Whitespace in new
    # files is not covered by git diff --check until staged — we run again
    # after add in publication. Here pre-commit check on tracked diffs.
    validation_ok = vcode == 0
    validation_reason = ""
    if not validation_ok:
        validation_reason = (vout or verr or "git diff --check failed").strip()

    if unexpected:
        return PostconditionResult(
            ok=False,
            unexpected_paths=unexpected,
            required_paths_ok=required_ok,
            validation_ok=validation_ok,
            changed_paths=changed,
            reason=(
                "POSTCONDITION_FAILED: unexpected paths outside allowed_paths: "
                + ", ".join(unexpected)
            ),
            final_status=FinalStatus.POSTCONDITION_FAILED,
        )

    if not required_ok:
        return PostconditionResult(
            ok=False,
            unexpected_paths=(),
            required_paths_ok=False,
            validation_ok=validation_ok,
            changed_paths=changed,
            reason=(
                "POSTCONDITION_FAILED: missing required paths: "
                + ", ".join(missing_required)
            ),
            final_status=FinalStatus.POSTCONDITION_FAILED,
        )

    if not validation_ok:
        return PostconditionResult(
            ok=False,
            unexpected_paths=(),
            required_paths_ok=True,
            validation_ok=False,
            changed_paths=changed,
            reason=f"VALIDATION_FAILED: {validation_reason}",
            final_status=FinalStatus.VALIDATION_FAILED,
        )

    # Изменения должны покрывать required (каждый required в changed или уже
    # committed — для pilot required создаётся Executor как new file → in changed).
    # Если worktree clean но required exists — возможно уже committed; для
    # publication_commit всё равно нужен diff. Если нет изменений и commit
    # запрошен — fail (nothing to commit).
    if prompt.publication_commit and not changed:
        return PostconditionResult(
            ok=False,
            unexpected_paths=(),
            required_paths_ok=True,
            validation_ok=True,
            changed_paths=(),
            reason="POSTCONDITION_FAILED: no changes to commit",
            final_status=FinalStatus.POSTCONDITION_FAILED,
        )

    return PostconditionResult(
        ok=True,
        unexpected_paths=(),
        required_paths_ok=True,
        validation_ok=True,
        changed_paths=changed,
        reason="postconditions ok",
        final_status=FinalStatus.WORK_PACKAGE_SUCCESS,
    )


def publish_exact_paths(
    prompt: BridgePrompt,
    *,
    executor_worktree: Path,
    paths_to_stage: Sequence[str],
    git_runner: GitRunner = default_git_runner,
) -> PublicationResult:
    """Exact-path add → commit → optional push → ls-remote verify."""
    wt = executor_worktree.resolve()
    commands: list[tuple[str, ...]] = []

    if not prompt.publication_commit:
        return PublicationResult(
            commit_created=False,
            local_head=None,
            push_attempted=False,
            remote_head=None,
            publication_verified=False,
            final_status=FinalStatus.EXECUTOR_PROCESS_EXITED_ZERO,
            reason="publication_commit=false; skipping commit/push",
            git_commands=(),
        )

    branch = prompt.target_branch or ""
    if branch in ("main", "master"):
        return PublicationResult(
            commit_created=False,
            local_head=None,
            push_attempted=False,
            remote_head=None,
            publication_verified=False,
            final_status=FinalStatus.FAIL_CLOSED,
            reason="refuse publication to main/master",
            git_commands=(),
        )

    # Только пересечение changed ∩ allowed, плюс required.
    stage = [p for p in paths_to_stage if p in set(prompt.allowed_paths)]
    for req in prompt.required_paths:
        if req not in stage:
            stage.append(req)
    stage = list(dict.fromkeys(stage))  # unique, preserve order

    if not stage:
        return PublicationResult(
            commit_created=False,
            local_head=None,
            push_attempted=False,
            remote_head=None,
            publication_verified=False,
            final_status=FinalStatus.POSTCONDITION_FAILED,
            reason="no exact paths to stage",
            git_commands=(),
        )

    # Запрет опасных add-форм.
    for p in stage:
        if p in FORBIDDEN_ADD_ARGS:
            return PublicationResult(
                commit_created=False,
                local_head=None,
                push_attempted=False,
                remote_head=None,
                publication_verified=False,
                final_status=FinalStatus.FAIL_CLOSED,
                reason=f"refusing forbidden add path arg: {p!r}",
                git_commands=(),
            )

    add_cmd = ("add", "--", *stage)
    commands.append(add_cmd)
    code, out, err = git_runner(list(add_cmd), wt)
    if code != 0:
        return PublicationResult(
            commit_created=False,
            local_head=None,
            push_attempted=False,
            remote_head=None,
            publication_verified=False,
            final_status=FinalStatus.PUBLICATION_FAILED,
            reason=f"git add failed: {err.strip() or out.strip()}",
            staged_paths=tuple(stage),
            git_commands=tuple(commands),
        )

    # diff --check после staging
    commands.append(("diff", "--cached", "--check"))
    vcode, vout, verr = git_runner(["diff", "--cached", "--check"], wt)
    if vcode != 0:
        return PublicationResult(
            commit_created=False,
            local_head=None,
            push_attempted=False,
            remote_head=None,
            publication_verified=False,
            final_status=FinalStatus.VALIDATION_FAILED,
            reason=f"git diff --cached --check failed: {(vout or verr).strip()}",
            staged_paths=tuple(stage),
            git_commands=tuple(commands),
        )

    msg = prompt.commit_message or "coordinator: automated commit"
    commit_cmd = ("commit", "-m", msg)
    commands.append(commit_cmd)
    ccode, cout, cerr = git_runner(list(commit_cmd), wt)
    if ccode != 0:
        return PublicationResult(
            commit_created=False,
            local_head=None,
            push_attempted=False,
            remote_head=None,
            publication_verified=False,
            final_status=FinalStatus.PUBLICATION_FAILED,
            reason=f"git commit failed: {cerr.strip() or cout.strip()}",
            staged_paths=tuple(stage),
            git_commands=tuple(commands),
        )

    commands.append(("rev-parse", "HEAD"))
    hcode, hout, _ = git_runner(["rev-parse", "HEAD"], wt)
    local_head = hout.strip() if hcode == 0 else None
    if not local_head:
        return PublicationResult(
            commit_created=True,
            local_head=None,
            push_attempted=False,
            remote_head=None,
            publication_verified=False,
            final_status=FinalStatus.PUBLICATION_UNVERIFIED,
            reason="commit ok but unable to read local HEAD",
            staged_paths=tuple(stage),
            git_commands=tuple(commands),
        )

    if not prompt.publication_push:
        return PublicationResult(
            commit_created=True,
            local_head=local_head,
            push_attempted=False,
            remote_head=None,
            publication_verified=False,
            final_status=FinalStatus.WORK_PACKAGE_SUCCESS,
            reason="commit created; push not requested",
            staged_paths=tuple(stage),
            git_commands=tuple(commands),
        )

    # Push: никогда force, никогда main.
    refspec = f"HEAD:refs/heads/{branch}"
    push_cmd = ("push", "origin", refspec)
    commands.append(push_cmd)
    pcode, pout, perr = git_runner(list(push_cmd), wt)
    if pcode != 0:
        return PublicationResult(
            commit_created=True,
            local_head=local_head,
            push_attempted=True,
            remote_head=None,
            publication_verified=False,
            final_status=FinalStatus.PUBLICATION_FAILED,
            reason=f"git push failed: {perr.strip() or pout.strip()}",
            staged_paths=tuple(stage),
            git_commands=tuple(commands),
        )

    ls_cmd = ("ls-remote", "origin", f"refs/heads/{branch}")
    commands.append(ls_cmd)
    lcode, lout, lerr = git_runner(list(ls_cmd), wt)
    remote_head = None
    if lcode == 0 and lout.strip():
        remote_head = lout.strip().split()[0].strip()

    if not remote_head:
        return PublicationResult(
            commit_created=True,
            local_head=local_head,
            push_attempted=True,
            remote_head=None,
            publication_verified=False,
            final_status=FinalStatus.PUBLICATION_UNVERIFIED,
            reason=f"unable to read remote tip after push: {lerr.strip()}",
            staged_paths=tuple(stage),
            git_commands=tuple(commands),
        )

    if remote_head != local_head:
        return PublicationResult(
            commit_created=True,
            local_head=local_head,
            push_attempted=True,
            remote_head=remote_head,
            publication_verified=False,
            final_status=FinalStatus.PUBLICATION_UNVERIFIED,
            reason=(
                f"remote SHA mismatch: local={local_head} remote={remote_head}"
            ),
            staged_paths=tuple(stage),
            git_commands=tuple(commands),
        )

    return PublicationResult(
        commit_created=True,
        local_head=local_head,
        push_attempted=True,
        remote_head=remote_head,
        publication_verified=True,
        final_status=FinalStatus.WORK_PACKAGE_SUCCESS,
        reason="commit+push verified",
        staged_paths=tuple(stage),
        git_commands=tuple(commands),
    )
