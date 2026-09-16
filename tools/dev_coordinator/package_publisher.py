"""Architect-side публикация bounded work package (transport only, без Executor).

Создаёт remote target branch (если отсутствует) и bridge commit с next-prompt.md.
Не вызывает Coordinator/Executor. Fail closed на любой небезопасный git шаг.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from tools.dev_coordinator.gitutil import (
    GitRunner,
    default_git_runner,
    read_origin_repo,
    read_remote_branch_tip,
)
from tools.dev_coordinator.managed_worktrees import derive_executor_worktree_path
from tools.dev_coordinator.parse import parse_next_prompt
from tools.dev_coordinator.runner_config import (
    REQUIRED_BRIDGE_PREFIX,
    RunnerConfig,
    load_runner_config,
)
from tools.dev_coordinator.safety import read_worktree_snapshot
from tools.dev_coordinator.transient import validate_transient_paths

# Запрещённые целевые ветки.
_FORBIDDEN_TARGET_BRANCHES = frozenset({"main", "master"})

# Допустимые hosted_ci политики.
_ALLOWED_HOSTED_CI = frozenset({"forbidden", "read_only", "informational"})

# Путь bridge-prompt внутри bridge repo.
_BRIDGE_PROMPT_PATH = "docs/agent-bridge/next-prompt.md"

# Подкоманды git, которые publisher никогда не должен вызывать.
_FORBIDDEN_GIT_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("reset", "--hard"),
    ("clean",),
    ("checkout",),
    ("switch",),
    ("rebase",),
    ("stash",),
    ("pull",),
    ("merge",),
)

_PATH_SEP = ","


@dataclass(frozen=True)
class WorkPackageSpec:
    """Декларативный ввод для публикации work package."""

    runner_config_path: Path
    bridge_repo: str
    target_repo: str
    base_sha: str
    target_branch: str
    bridge_branch: str
    prompt_id: str
    allowed_paths: tuple[str, ...]
    required_paths: tuple[str, ...]
    transient_paths: tuple[str, ...]
    commit_message: str
    hosted_ci: str
    publication_commit: bool
    publication_push: bool
    max_executor_runs: int
    instruction_body: str
    dry_run: bool = False


@dataclass(frozen=True)
class CheckoutSnapshot:
    """Снимок primary checkout до/после (доказательство неизменности)."""

    head_sha: Optional[str]
    branch: Optional[str]
    status_porcelain: str
    cached_diff_stat: str


@dataclass(frozen=True)
class PublicationOutcome:
    """Итог публикации (machine-readable + поля для human summary)."""

    ok: bool
    dry_run: bool
    reason: str
    target_repo: str
    target_branch: str
    target_worktree: str
    base_sha: str
    target_remote_sha: Optional[str]
    bridge_repo: str
    bridge_branch: str
    bridge_remote_sha: Optional[str]
    prompt_id: str
    next_prompt_text: str
    resumed_target: bool = False
    resumed_bridge: bool = False
    git_commands: tuple[tuple[str, ...], ...] = ()
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """JSON-сериализуемый результат."""
        return {
            "ok": self.ok,
            "dry_run": self.dry_run,
            "reason": self.reason,
            "target_repo": self.target_repo,
            "target_branch": self.target_branch,
            "target_worktree": self.target_worktree,
            "base_sha": self.base_sha,
            "target_remote_sha": self.target_remote_sha,
            "bridge_repo": self.bridge_repo,
            "bridge_branch": self.bridge_branch,
            "bridge_remote_sha": self.bridge_remote_sha,
            "prompt_id": self.prompt_id,
            "resumed_target": self.resumed_target,
            "resumed_bridge": self.resumed_bridge,
            "errors": list(self.errors),
        }

    def format_human(self) -> str:
        """Краткий human-readable отчёт."""
        lines = [
            f"ok={self.ok} dry_run={self.dry_run}",
            f"reason: {self.reason}",
            f"target: {self.target_repo}@{self.target_branch} "
            f"sha={self.target_remote_sha or '(none)'}",
            f"bridge: {self.bridge_repo}@{self.bridge_branch} "
            f"sha={self.bridge_remote_sha or '(none)'}",
            f"target_worktree: {self.target_worktree}",
            f"prompt_id: {self.prompt_id}",
        ]
        if self.resumed_target:
            lines.append("target: reused existing remote at base_sha")
        if self.resumed_bridge:
            lines.append("bridge: idempotent reuse (identical package)")
        return "\n".join(lines)


@dataclass
class _GitSession:
    """Обёртка git_runner с аудитом запрещённых команд."""

    git_runner: GitRunner
    commands: list[tuple[str, ...]] = field(default_factory=list)

    def run(
        self,
        args: Sequence[str],
        cwd: Path,
        *,
        env: Optional[dict[str, str]] = None,
    ) -> tuple[int, str, str]:
        cmd = tuple(str(a) for a in args)
        _assert_git_command_allowed(cmd)
        self.commands.append(cmd)
        if env:
            return _git_runner_with_env(self.git_runner, cmd, cwd, env)
        return self.git_runner(list(cmd), cwd)


def _git_runner_with_env(
    base_runner: GitRunner,
    args: Sequence[str],
    cwd: Path,
    extra_env: dict[str, str],
) -> tuple[int, str, str]:
    """Вызов git с GIT_INDEX_FILE и др. env-переменными.

    Injected test runner (не default_git_runner) получает те же args без env:
    FakeRemoteState симулирует plumbing. Реальный git — только default_git_runner.
    """
    if base_runner is not default_git_runner:
        return base_runner(list(args), cwd)

    import subprocess

    env = os.environ.copy()
    env.update(extra_env)
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _assert_git_command_allowed(cmd: tuple[str, ...]) -> None:
    """Fail fast если команда в списке запрещённых."""
    if not cmd:
        return
    for forbidden in _FORBIDDEN_GIT_PREFIXES:
        if len(cmd) >= len(forbidden) and tuple(cmd[: len(forbidden)]) == forbidden:
            raise ValueError(f"forbidden git command: {' '.join(cmd)}")
    if cmd[0] == "push":
        for token in cmd[1:]:
            if token in ("--force", "-f", "--force-with-lease"):
                raise ValueError(f"forbidden force push: {' '.join(cmd)}")


def resolve_bridge_branch(
    *,
    bridge_branch: Optional[str],
    package_id: Optional[str],
) -> str:
    """Определить bridge branch из явного имени или package_id."""
    if bridge_branch:
        branch = bridge_branch.strip()
        if not branch:
            raise ValueError("empty bridge_branch")
        return branch
    if package_id:
        pid = package_id.strip()
        if not pid:
            raise ValueError("empty package_id")
        return f"{REQUIRED_BRIDGE_PREFIX}{pid}"
    raise ValueError("bridge_branch or package_id is required")


def _join_paths(paths: Sequence[str]) -> str:
    return _PATH_SEP.join(paths)


def render_next_prompt(
    *,
    spec: WorkPackageSpec,
    target_worktree: Path,
) -> str:
    """Собрать next-prompt.md с flat front matter (round-trip parse_next_prompt)."""
    lines = [
        "---",
        "coord_version: 1",
        "state: EXECUTOR_READY",
        f"prompt_id: {spec.prompt_id}",
        f"target_repo: {spec.target_repo}",
        f"target_branch: {spec.target_branch}",
        f"target_worktree: {target_worktree}",
        f"base_sha: {spec.base_sha}",
        f"hosted_ci: {spec.hosted_ci}",
        f"max_executor_runs: {spec.max_executor_runs}",
        f"allowed_paths: {_join_paths(spec.allowed_paths)}",
        f"required_paths: {_join_paths(spec.required_paths)}",
        f"publication_commit: {'true' if spec.publication_commit else 'false'}",
        f"publication_push: {'true' if spec.publication_push else 'false'}",
        f"commit_message: {spec.commit_message}",
    ]
    if spec.transient_paths:
        lines.append(f"transient_paths: {_join_paths(spec.transient_paths)}")
    lines.append("---")
    lines.append("")
    body = spec.instruction_body.rstrip("\n")
    if body:
        lines.append(body)
    return "\n".join(lines) + "\n"


def read_checkout_snapshot(
    repo_clone: Path,
    git: _GitSession,
) -> CheckoutSnapshot:
    """Read-only снимок primary checkout."""
    snap = read_worktree_snapshot(repo_clone, git_runner=git.git_runner)
    code_d, out_d, _ = git.run(["diff", "--cached", "--stat"], repo_clone)
    cached = out_d if code_d == 0 else ""
    return CheckoutSnapshot(
        head_sha=snap.head_sha,
        branch=snap.branch,
        status_porcelain=snap.status_short,
        cached_diff_stat=cached,
    )


def snapshots_equal(a: CheckoutSnapshot, b: CheckoutSnapshot) -> bool:
    """Сравнение снимков (byte/status-identical для тестов)."""
    return (
        a.head_sha == b.head_sha
        and a.branch == b.branch
        and a.status_porcelain == b.status_porcelain
        and a.cached_diff_stat == b.cached_diff_stat
    )


def _normalize_sha(sha: str) -> str:
    """Требовать полный 40-символьный hex SHA (без abbreviated)."""
    text = sha.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", text):
        raise ValueError(
            f"invalid git SHA: {sha!r} (must be full 40-character hexadecimal)"
        )
    return text


def _validate_spec_inputs(spec: WorkPackageSpec, config: RunnerConfig) -> list[str]:
    """Локальная валидация до любых remote/git mutation."""
    errors: list[str] = []

    if spec.bridge_repo not in config.repositories:
        errors.append(f"bridge_repo not in runner allowlist: {spec.bridge_repo}")
    if spec.target_repo not in config.repositories:
        errors.append(f"target_repo not in runner allowlist: {spec.target_repo}")

    if spec.target_branch in _FORBIDDEN_TARGET_BRANCHES:
        errors.append(f"forbidden target branch: {spec.target_branch!r}")
    if spec.target_branch.startswith("coord/bridge/"):
        errors.append(
            f"target branch in coord/bridge namespace: {spec.target_branch!r}"
        )
    if not spec.bridge_branch.startswith(REQUIRED_BRIDGE_PREFIX):
        errors.append(
            f"bridge branch outside namespace: {spec.bridge_branch!r}"
        )

    if spec.hosted_ci not in _ALLOWED_HOSTED_CI:
        errors.append(f"unsupported hosted_ci: {spec.hosted_ci!r}")

    if spec.max_executor_runs != 1:
        errors.append(
            f"max_executor_runs must be exactly 1: {spec.max_executor_runs}"
        )

    if not spec.allowed_paths:
        errors.append("allowed_paths must be non-empty")
    if not spec.required_paths:
        errors.append("required_paths must be non-empty")
    for req in spec.required_paths:
        if req not in spec.allowed_paths:
            errors.append(f"required_path not in allowed_paths: {req}")
    if not spec.commit_message.strip():
        errors.append("commit_message must be non-empty")
    if spec.publication_push and not spec.publication_commit:
        errors.append("publication_push requires publication_commit=true")

    t_err = validate_transient_paths(
        spec.transient_paths,
        allowed=spec.allowed_paths,
        required=spec.required_paths,
    )
    if t_err:
        errors.append(t_err)

    try:
        _normalize_sha(spec.base_sha)
    except ValueError as exc:
        errors.append(str(exc))

    if not spec.prompt_id.strip():
        errors.append("prompt_id must be non-empty")

    return errors


def _verify_origin(
    repo_clone: Path,
    expected: str,
    label: str,
    git: _GitSession,
) -> Optional[str]:
    """Проверить canonical origin; вернуть текст ошибки или None."""
    canonical, raw = read_origin_repo(repo_clone, git_runner=git.git_runner)
    if not canonical:
        return f"{label}: unable to canonicalize origin URL: {raw!r}"
    if canonical != expected:
        return f"{label}: origin mismatch: expected={expected} actual={canonical}"
    return None


def _verify_commit_exists(repo_clone: Path, sha: str, git: _GitSession) -> Optional[str]:
    """Проверить, что SHA — существующий commit в clone."""
    code, _, err = git.run(["cat-file", "-e", f"{sha}^{{commit}}"], repo_clone)
    if code != 0:
        return f"base_sha is not a commit in {repo_clone}: {sha} ({err.strip()})"
    return None


def _read_remote_prompt_at_tip(
    repo_clone: Path,
    branch: str,
    tip_sha: str,
    git: _GitSession,
) -> tuple[Optional[str], Optional[str]]:
    """Прочитать next-prompt.md с remote tip (read-only git show)."""
    code, out, err = git.run(
        ["show", f"{tip_sha}:{_BRIDGE_PROMPT_PATH}"],
        repo_clone,
    )
    if code != 0:
        return None, (err or out or "git show failed").strip()
    return out, None


def _create_commit_with_prompt(
    repo_clone: Path,
    *,
    parent_sha: str,
    prompt_text: str,
    message: str,
    git: _GitSession,
) -> tuple[Optional[str], Optional[str]]:
    """Изолированный commit-tree: временный GIT_INDEX_FILE, объекты в repo DB."""
    git_dir = _resolve_git_dir(repo_clone)
    if git_dir is None:
        return None, f"unable to resolve git dir for {repo_clone}"

    # Только index изолирован; blob/tree/commit пишутся в object DB clone,
    # чтобы push мог найти commit после выхода из helper.
    with tempfile.TemporaryDirectory(prefix="pkg-pub-") as tmp:
        index_file = Path(tmp) / "index"
        prompt_file = Path(tmp) / "prompt-body.md"
        prompt_file.write_text(prompt_text, encoding="utf-8")
        env = {
            "GIT_INDEX_FILE": str(index_file),
        }

        code_h, blob_sha, err_h = git.run(
            ["hash-object", "-w", str(prompt_file)],
            repo_clone,
            env=env,
        )
        if code_h != 0:
            return None, f"hash-object failed: {err_h.strip()}"
        blob_sha = blob_sha.strip()

        # Parent tree → обновить один файл.
        code_r, _, err_r = git.run(
            ["read-tree", parent_sha],
            repo_clone,
            env=env,
        )
        if code_r != 0:
            # Parent может быть empty — попробуем read-tree с tree из commit.
            code_ct, tree_out, _ = git.run(
                ["rev-parse", f"{parent_sha}^{{tree}}"],
                repo_clone,
            )
            if code_ct != 0:
                return None, f"unable to read parent tree: {err_r.strip()}"
            parent_tree = tree_out.strip()
            code_r2, _, err_r2 = git.run(
                ["read-tree", parent_tree],
                repo_clone,
                env=env,
            )
            if code_r2 != 0:
                return None, f"read-tree failed: {err_r2.strip()}"

        code_u, _, err_u = git.run(
            [
                "update-index",
                "--add",
                "--cacheinfo",
                "100644",
                blob_sha,
                _BRIDGE_PROMPT_PATH,
            ],
            repo_clone,
            env=env,
        )
        if code_u != 0:
            return None, f"update-index failed: {err_u.strip()}"

        code_w, tree_sha, err_w = git.run(["write-tree"], repo_clone, env=env)
        if code_w != 0:
            return None, f"write-tree failed: {err_w.strip()}"
        tree_sha = tree_sha.strip()

        code_c, commit_sha, err_c = git.run(
            ["commit-tree", tree_sha, "-p", parent_sha, "-m", message],
            repo_clone,
            env=env,
        )
        if code_c != 0:
            return None, f"commit-tree failed: {err_c.strip()}"
        return commit_sha.strip(), None


def _resolve_git_dir(repo_clone: Path) -> Optional[Path]:
    """Найти .git directory для clone (поддержка worktree gitfile)."""
    git_path = repo_clone / ".git"
    if git_path.is_dir():
        return git_path.resolve()
    if git_path.is_file():
        text = git_path.read_text(encoding="utf-8").strip()
        if text.startswith("gitdir:"):
            return Path(text.split(":", 1)[1].strip()).resolve()
    return None


def _push_ref(
    repo_clone: Path,
    refspec: str,
    git: _GitSession,
) -> tuple[bool, str]:
    """Non-force push одного refspec."""
    code, out, err = git.run(["push", "origin", refspec], repo_clone)
    if code != 0:
        return False, (err or out or "git push failed").strip()
    return True, "ok"


def publish_work_package(
    spec: WorkPackageSpec,
    *,
    git_runner: GitRunner = default_git_runner,
) -> PublicationOutcome:
    """Опубликовать work package (или dry-run без mutation)."""
    git = _GitSession(git_runner=git_runner)
    errors: list[str] = []

    try:
        config = load_runner_config(spec.runner_config_path)
    except (OSError, ValueError) as exc:
        return _fail_outcome(spec, (), [str(exc)], "config load failed")

    input_errors = _validate_spec_inputs(spec, config)
    if input_errors:
        return _fail_outcome(spec, (), input_errors, "validation failed")

    base_sha = _normalize_sha(spec.base_sha)
    target_worktree = derive_executor_worktree_path(
        config.managed_worktree_root,
        spec.target_repo,
        spec.target_branch,
    )

    prompt_text = render_next_prompt(spec=spec, target_worktree=target_worktree)
    parsed = parse_next_prompt(prompt_text)
    if parsed.parse_error:
        return _fail_outcome(
            spec,
            (),
            [f"rendered prompt invalid: {parsed.parse_error}"],
            "prompt round-trip failed",
            next_prompt_text=prompt_text,
            target_worktree=str(target_worktree),
        )

    bridge_clone = config.repo_path(spec.bridge_repo)
    target_clone = config.repo_path(spec.target_repo)
    if bridge_clone is None or target_clone is None:
        return _fail_outcome(spec, (), ["repository clone path missing"], "config error")

    bridge_before = read_checkout_snapshot(bridge_clone, git)
    target_before: Optional[CheckoutSnapshot] = None
    if target_clone != bridge_clone:
        target_before = read_checkout_snapshot(target_clone, git)
    else:
        target_before = bridge_before

    # --- 1. validate everything possible locally ---
    for label, clone, repo in (
        ("bridge", bridge_clone, spec.bridge_repo),
        ("target", target_clone, spec.target_repo),
    ):
        err = _verify_origin(clone, repo, label, git)
        if err:
            errors.append(err)
    if target_clone == bridge_clone and len(errors) == 2:
        # Дублирующие ошибки для одного clone — оставляем одну.
        errors = [errors[0]]

    commit_err = _verify_commit_exists(target_clone, base_sha, git)
    if commit_err:
        errors.append(commit_err)

    if errors:
        return _fail_outcome(
            spec,
            tuple(git.commands),
            errors,
            "local validation failed",
            next_prompt_text=prompt_text,
            target_worktree=str(target_worktree),
        )

    # --- 2. inspect target remote branch ---
    target_remote = read_remote_branch_tip(
        target_clone, spec.target_branch, git_runner=git.git_runner
    )
    resumed_target = False

    if target_remote is not None and target_remote != base_sha:
        return _fail_outcome(
            spec,
            tuple(git.commands),
            [
                f"target remote SHA mismatch: expected={base_sha} "
                f"actual={target_remote}"
            ],
            "target remote at unexpected SHA",
            next_prompt_text=prompt_text,
            target_worktree=str(target_worktree),
        )
    if target_remote == base_sha:
        resumed_target = True

    # --- 3. inspect bridge remote branch ---
    bridge_remote = read_remote_branch_tip(
        bridge_clone, spec.bridge_branch, git_runner=git.git_runner
    )
    resumed_bridge = False
    bridge_commit_sha: Optional[str] = None

    if bridge_remote is not None:
        existing_prompt, show_err = _read_remote_prompt_at_tip(
            bridge_clone, spec.bridge_branch, bridge_remote, git
        )
        if show_err:
            return _fail_outcome(
                spec,
                tuple(git.commands),
                [f"unable to read existing bridge prompt: {show_err}"],
                "bridge inspection failed",
                next_prompt_text=prompt_text,
                target_worktree=str(target_worktree),
            )
        if existing_prompt is not None and existing_prompt != prompt_text:
            return _fail_outcome(
                spec,
                tuple(git.commands),
                ["existing bridge package content differs from requested package"],
                "bridge content mismatch",
                next_prompt_text=prompt_text,
                target_worktree=str(target_worktree),
            )
        if existing_prompt == prompt_text:
            resumed_bridge = True
            bridge_commit_sha = bridge_remote

    if spec.dry_run:
        return PublicationOutcome(
            ok=True,
            dry_run=True,
            reason="dry-run ok",
            target_repo=spec.target_repo,
            target_branch=spec.target_branch,
            target_worktree=str(target_worktree),
            base_sha=base_sha,
            target_remote_sha=target_remote or base_sha,
            bridge_repo=spec.bridge_repo,
            bridge_branch=spec.bridge_branch,
            bridge_remote_sha=bridge_commit_sha or "(would create)",
            prompt_id=spec.prompt_id,
            next_prompt_text=prompt_text,
            resumed_target=resumed_target,
            resumed_bridge=resumed_bridge,
            git_commands=tuple(git.commands),
        )

    # --- 4. create target remote branch if absent ---
    if target_remote is None:
        refspec = f"{base_sha}:refs/heads/{spec.target_branch}"
        ok_push, push_reason = _push_ref(target_clone, refspec, git)
        if not ok_push:
            return _fail_outcome(
                spec,
                tuple(git.commands),
                [f"target branch creation failed: {push_reason}"],
                "target push failed",
                next_prompt_text=prompt_text,
                target_worktree=str(target_worktree),
            )

    # --- 5. verify exact target remote SHA ---
    target_remote_after = read_remote_branch_tip(
        target_clone, spec.target_branch, git_runner=git.git_runner
    )
    if target_remote_after != base_sha:
        return _fail_outcome(
            spec,
            tuple(git.commands),
            [
                f"target remote verify failed: expected={base_sha} "
                f"actual={target_remote_after}"
            ],
            "target verify failed",
            next_prompt_text=prompt_text,
            target_worktree=str(target_worktree),
        )

    # --- 6–8. bridge commit + publish (если ещё не idempotent) ---
    if not resumed_bridge:
        if bridge_remote is not None:
            parent_sha = bridge_remote
        else:
            code_h, head_out, err_h = git.run(["rev-parse", "HEAD"], bridge_clone)
            if code_h != 0:
                return _fail_outcome(
                    spec,
                    tuple(git.commands),
                    [f"unable to read bridge clone HEAD: {err_h.strip()}"],
                    "bridge parent resolution failed",
                    next_prompt_text=prompt_text,
                    target_worktree=str(target_worktree),
                )
            parent_sha = head_out.strip()

        bridge_commit_sha, commit_err = _create_commit_with_prompt(
            bridge_clone,
            parent_sha=parent_sha,
            prompt_text=prompt_text,
            message=f"coord: publish {spec.prompt_id}",
            git=git,
        )
        if commit_err or not bridge_commit_sha:
            return _fail_outcome(
                spec,
                tuple(git.commands),
                [commit_err or "bridge commit failed"],
                "bridge commit failed",
                next_prompt_text=prompt_text,
                target_worktree=str(target_worktree),
            )

        refspec = f"{bridge_commit_sha}:refs/heads/{spec.bridge_branch}"
        ok_push, push_reason = _push_ref(bridge_clone, refspec, git)
        if not ok_push:
            return _fail_outcome(
                spec,
                tuple(git.commands),
                [f"bridge push failed: {push_reason}"],
                "bridge push failed",
                next_prompt_text=prompt_text,
                target_worktree=str(target_worktree),
            )

    # --- 9. verify bridge remote SHA ---
    bridge_remote_after = read_remote_branch_tip(
        bridge_clone, spec.bridge_branch, git_runner=git.git_runner
    )
    if not bridge_remote_after:
        return _fail_outcome(
            spec,
            tuple(git.commands),
            ["bridge remote missing after publish"],
            "bridge verify failed",
            next_prompt_text=prompt_text,
            target_worktree=str(target_worktree),
        )
    if bridge_commit_sha and bridge_remote_after != bridge_commit_sha:
        return _fail_outcome(
            spec,
            tuple(git.commands),
            [
                f"bridge remote verify failed: expected={bridge_commit_sha} "
                f"actual={bridge_remote_after}"
            ],
            "bridge verify failed",
            next_prompt_text=prompt_text,
            target_worktree=str(target_worktree),
        )

    # --- primary checkout preservation ---
    bridge_after = read_checkout_snapshot(bridge_clone, git)
    if not snapshots_equal(bridge_before, bridge_after):
        return _fail_outcome(
            spec,
            tuple(git.commands),
            ["bridge primary checkout was modified"],
            "checkout integrity failed",
            next_prompt_text=prompt_text,
            target_worktree=str(target_worktree),
        )
    if target_clone != bridge_clone:
        target_after = read_checkout_snapshot(target_clone, git)
        if not snapshots_equal(target_before, target_after):
            return _fail_outcome(
                spec,
                tuple(git.commands),
                ["target primary checkout was modified"],
                "checkout integrity failed",
                next_prompt_text=prompt_text,
                target_worktree=str(target_worktree),
            )

    return PublicationOutcome(
        ok=True,
        dry_run=False,
        reason="published",
        target_repo=spec.target_repo,
        target_branch=spec.target_branch,
        target_worktree=str(target_worktree),
        base_sha=base_sha,
        target_remote_sha=target_remote_after,
        bridge_repo=spec.bridge_repo,
        bridge_branch=spec.bridge_branch,
        bridge_remote_sha=bridge_remote_after,
        prompt_id=spec.prompt_id,
        next_prompt_text=prompt_text,
        resumed_target=resumed_target,
        resumed_bridge=resumed_bridge,
        git_commands=tuple(git.commands),
    )


def _fail_outcome(
    spec: WorkPackageSpec,
    commands: tuple[tuple[str, ...], ...],
    errors: list[str],
    reason: str,
    *,
    next_prompt_text: str = "",
    target_worktree: str = "",
) -> PublicationOutcome:
    """Собрать fail-closed outcome."""
    return PublicationOutcome(
        ok=False,
        dry_run=spec.dry_run,
        reason=reason,
        target_repo=spec.target_repo,
        target_branch=spec.target_branch,
        target_worktree=target_worktree,
        base_sha=spec.base_sha,
        target_remote_sha=None,
        bridge_repo=spec.bridge_repo,
        bridge_branch=spec.bridge_branch,
        bridge_remote_sha=None,
        prompt_id=spec.prompt_id,
        next_prompt_text=next_prompt_text,
        git_commands=commands,
        errors=tuple(errors),
    )


def format_result_json(outcome: PublicationOutcome) -> str:
    """Machine-readable JSON (одна строка для скриптов)."""
    return json.dumps(outcome.to_dict(), sort_keys=True)
