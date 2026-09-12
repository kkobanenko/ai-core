"""CLI Coordinator v0.2: launch + postconditions + deterministic publication."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Optional, Sequence
import sys

from tools.dev_coordinator.claim import try_acquire_claim
from tools.dev_coordinator.decision import decide
from tools.dev_coordinator.executor import (
    compose_executor_prompt,
    launch_executor_once,
    tail_text,
)
from tools.dev_coordinator.locks import ProcessLock
from tools.dev_coordinator.models import (
    Action,
    CoordState,
    Decision,
    FinalStatus,
    RunResult,
)
from tools.dev_coordinator.parse import parse_next_prompt
from tools.dev_coordinator.paths import default_state_dir, ensure_state_layout
from tools.dev_coordinator.publication import (
    evaluate_postconditions,
    publish_exact_paths,
)
from tools.dev_coordinator.safety import (
    GitRunner,
    _default_git_runner,
    verify_bridge_source,
)
from tools.dev_coordinator.transient import (
    classify_and_cleanup_transients,
    snapshot_transients,
)


DEFAULT_BRIDGE_REL = Path("docs/agent-bridge/next-prompt.md")


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_executor_governance(executor_worktree: Path) -> str:
    chunks: list[str] = []
    agents = executor_worktree / "AGENTS.md"
    if agents.is_file():
        chunks.append(agents.read_text(encoding="utf-8"))
    rules_dir = executor_worktree / ".cursor" / "rules"
    if rules_dir.is_dir():
        for path in sorted(rules_dir.glob("**/*")):
            if path.is_file() and path.suffix in {".md", ".mdc", ".txt"}:
                chunks.append(
                    f"## {path.relative_to(executor_worktree)}\n\n"
                    + path.read_text(encoding="utf-8")
                )
    if not chunks:
        return "(no AGENTS.md / .cursor/rules found in executor_worktree)"
    return "\n\n".join(chunks)


def _save_executor_log(
    state_dir: Path, prompt_id: Optional[str], stdout: str, stderr: str
) -> Optional[str]:
    ensure_state_layout(state_dir)
    log_dir = state_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_id = (prompt_id or "unknown").replace("/", "_")[:80]
    path = log_dir / f"{safe_id}-{int(time.time())}.log"
    try:
        path.write_text(
            "=== stdout ===\n"
            + tail_text(stdout)
            + "\n\n=== stderr ===\n"
            + tail_text(stderr)
            + "\n",
            encoding="utf-8",
        )
        return str(path)
    except OSError:
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dev_coordinator",
        description=(
            "Deterministic Coordinator v0.2 over docs/agent-bridge. "
            "Owns postcondition validation + exact-path commit/push."
        ),
    )
    parser.add_argument("--mode", choices=("shadow", "launch"), default="shadow")
    parser.add_argument("--once", action="store_true", default=True)
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--executor-worktree", type=Path, default=None)
    parser.add_argument("--bridge-worktree", type=Path, default=None)
    parser.add_argument("--bridge-prompt", type=Path, default=None)
    parser.add_argument("--state-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--agent-bin", default="agent")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="DEBUG/shadow only; launch+allow-dirty fails closed",
    )
    return parser


def run_once(
    *,
    mode: str,
    repo_root: Path,
    executor_worktree: Path,
    bridge_prompt_path: Path,
    bridge_worktree: Optional[Path] = None,
    agent_bin: str = "agent",
    allow_dirty: bool = False,
    launch: bool = True,
    state_dir: Optional[Path] = None,
    git_runner: Optional[GitRunner] = None,
    executor_runner=None,
) -> RunResult:
    """Одна оценка + optional launch + postconditions + publication."""
    t0 = time.monotonic()
    messages: list[str] = []
    runner = git_runner or _default_git_runner
    state = (state_dir or default_state_dir()).resolve()

    def _elapsed() -> float:
        return round(time.monotonic() - t0, 3)

    def _early(
        decision: Decision,
        final: FinalStatus,
        **extra,
    ) -> RunResult:
        return RunResult(
            mode=mode,
            decision=decision,
            executor_launched=False,
            executor_exit_code=None,
            messages=tuple(messages + [decision.reason]),
            final_status=final,
            elapsed_seconds=_elapsed(),
            **extra,
        )

    if not bridge_prompt_path.is_file():
        decision = Decision(
            action=Action.FAIL_CLOSED,
            state=CoordState.HUMAN_REQUIRED,
            reason=f"bridge prompt not found: {bridge_prompt_path}",
            would_launch=False,
            mutations=(),
        )
        return _early(decision, FinalStatus.FAIL_CLOSED)

    if mode == "launch" and bridge_worktree is None:
        decision = Decision(
            action=Action.FAIL_CLOSED,
            state=CoordState.HUMAN_REQUIRED,
            reason="--bridge-worktree is required for launch mode",
            would_launch=False,
            mutations=(),
        )
        return _early(decision, FinalStatus.FAIL_CLOSED)

    text = _load_text(bridge_prompt_path)
    prompt = parse_next_prompt(text)
    messages.append(
        f"parsed has_metadata={prompt.has_metadata} state={prompt.state} "
        f"parse_error={prompt.parse_error!r}"
    )

    if bridge_worktree is not None:
        expected_repo = prompt.target_repo if prompt.has_metadata else "kkobanenko/ai-core"
        if prompt.state == CoordState.WAIT and not prompt.target_repo:
            expected_repo = "kkobanenko/ai-core"
        bridge_report = verify_bridge_source(
            bridge_worktree=bridge_worktree,
            bridge_prompt_path=bridge_prompt_path,
            expected_repo=expected_repo,
            mode=mode,
            git_runner=runner,
            require_remote_match=(mode == "launch"),
        )
        if not bridge_report.ok:
            if mode == "launch":
                decision = Decision(
                    action=Action.NONE,
                    state=CoordState.HUMAN_REQUIRED,
                    reason="bridge source verification failed: "
                    + "; ".join(bridge_report.reasons),
                    would_launch=False,
                    mutations=(),
                    safety=bridge_report,
                )
                return _early(decision, FinalStatus.HUMAN_REQUIRED)
            messages.append(
                "bridge verification issues (shadow): "
                + "; ".join(bridge_report.reasons)
            )

    decision = decide(
        prompt,
        mode=mode,
        primary_repo=repo_root,
        executor_worktree=executor_worktree,
        allow_dirty=allow_dirty,
        git_runner=runner,
    )
    messages.append(f"decision action={decision.action.value} reason={decision.reason}")

    if mode == "shadow":
        final = FinalStatus.SHADOW_OK
        if prompt.state == CoordState.WAIT:
            final = FinalStatus.WAIT_OK
        elif decision.action == Action.FAIL_CLOSED:
            final = FinalStatus.FAIL_CLOSED
        elif decision.state == CoordState.HUMAN_REQUIRED:
            final = FinalStatus.HUMAN_REQUIRED
        return RunResult(
            mode=mode,
            decision=decision,
            executor_launched=False,
            executor_exit_code=None,
            messages=tuple(messages),
            final_status=final,
            elapsed_seconds=_elapsed(),
        )

    if not (
        launch
        and mode == "launch"
        and decision.action == Action.LAUNCH_EXECUTOR
        and decision.would_launch
    ):
        final = FinalStatus.FAIL_CLOSED
        if decision.state == CoordState.HUMAN_REQUIRED:
            final = FinalStatus.HUMAN_REQUIRED
        elif prompt.state == CoordState.WAIT:
            final = FinalStatus.WAIT_OK
        return RunResult(
            mode=mode,
            decision=decision,
            executor_launched=False,
            executor_exit_code=None,
            messages=tuple(messages),
            final_status=final,
            elapsed_seconds=_elapsed(),
        )

    lock = ProcessLock(state_dir=state, non_blocking=True)
    if not lock.acquire():
        decision = Decision(
            action=Action.NONE,
            state=CoordState.HUMAN_REQUIRED,
            reason="another Coordinator holds the process lock; refusing launch",
            would_launch=False,
            mutations=(),
        )
        return _early(decision, FinalStatus.HUMAN_REQUIRED)

    executor_launched = False
    exit_code: Optional[int] = None
    stdout_tail: Optional[str] = None
    stderr_tail: Optional[str] = None
    log_path: Optional[str] = None
    post_ok: Optional[bool] = None
    unexpected: tuple[str, ...] = ()
    required_ok: Optional[bool] = None
    validation_ok: Optional[bool] = None
    commit_created = False
    local_head: Optional[str] = None
    push_attempted = False
    remote_head: Optional[str] = None
    publication_verified = False
    final_status = FinalStatus.FAIL_CLOSED

    try:
        claim = try_acquire_claim(prompt, state_dir=state)
        messages.append(
            f"claim acquired={claim.acquired} hash={claim.identity_hash} "
            f"reason={claim.reason}"
        )
        if not claim.acquired:
            decision = Decision(
                action=Action.NONE,
                state=CoordState.HUMAN_REQUIRED,
                reason=claim.reason,
                would_launch=False,
                mutations=(),
            )
            return RunResult(
                mode=mode,
                decision=decision,
                executor_launched=False,
                executor_exit_code=None,
                messages=tuple(messages),
                final_status=FinalStatus.HUMAN_REQUIRED,
                elapsed_seconds=_elapsed(),
            )

        # v0.2.1: baseline snapshot для declared transient paths.
        baselines = ()
        if prompt.transient_paths:
            baselines, snap_err = snapshot_transients(
                prompt.transient_paths,
                executor_worktree=executor_worktree,
                git_runner=runner,
            )
            if snap_err:
                decision = Decision(
                    action=Action.FAIL_CLOSED,
                    state=CoordState.HUMAN_REQUIRED,
                    reason=snap_err,
                    would_launch=False,
                    mutations=("claim",),
                )
                messages.append(snap_err)
                return RunResult(
                    mode=mode,
                    decision=decision,
                    executor_launched=False,
                    executor_exit_code=None,
                    messages=tuple(messages),
                    final_status=FinalStatus.FAIL_CLOSED,
                    declared_transient_paths=prompt.transient_paths,
                    elapsed_seconds=_elapsed(),
                )
            messages.append(
                "transient baseline ok: " + ",".join(prompt.transient_paths)
            )

        governance = load_executor_governance(executor_worktree)
        composed = compose_executor_prompt(
            governance_text=governance,
            bridge_prompt=prompt,
        )
        outcome = launch_executor_once(
            prompt_text=composed,
            workspace=executor_worktree,
            agent_bin=agent_bin,
            runner=executor_runner,
        )
        executor_launched = True
        exit_code = outcome.exit_code
        stdout_tail = tail_text(outcome.stdout)
        stderr_tail = tail_text(outcome.stderr)
        log_path = _save_executor_log(
            state, prompt.prompt_id, outcome.stdout, outcome.stderr
        )
        messages.append(f"executor exit_code={exit_code}")
        if log_path:
            messages.append(f"executor_log_path={log_path}")

        # Exit 0 ≠ success. Nonzero → no publication.
        if exit_code != 0:
            final_status = FinalStatus.EXECUTOR_NONZERO
            decision = Decision(
                action=Action.LAUNCH_EXECUTOR,
                state=CoordState.HUMAN_REQUIRED,
                reason=f"executor nonzero exit={exit_code}; no publication",
                would_launch=True,
                mutations=("claim", "launch_executor"),
                safety=decision.safety,
            )
            messages.append(decision.reason)
            return RunResult(
                mode=mode,
                decision=decision,
                executor_launched=True,
                executor_exit_code=exit_code,
                messages=tuple(messages),
                final_status=final_status,
                elapsed_seconds=_elapsed(),
                executor_stdout_tail=stdout_tail,
                executor_stderr_tail=stderr_tail,
                executor_log_path=log_path,
            )

        # Нужны postconditions если есть allowed/required/transient или publication.
        need_post = bool(
            prompt.allowed_paths
            or prompt.required_paths
            or prompt.transient_paths
            or prompt.publication_commit
            or prompt.publication_push
        )
        if not need_post:
            final_status = FinalStatus.EXECUTOR_PROCESS_EXITED_ZERO
            decision = Decision(
                action=Action.LAUNCH_EXECUTOR,
                state=CoordState.EXECUTOR_READY,
                reason=(
                    "executor exited 0; no publication contract; "
                    "NOT work-package success"
                ),
                would_launch=True,
                mutations=("claim", "launch_executor"),
                safety=decision.safety,
            )
            messages.append(decision.reason)
            return RunResult(
                mode=mode,
                decision=decision,
                executor_launched=True,
                executor_exit_code=exit_code,
                messages=tuple(messages),
                final_status=final_status,
                elapsed_seconds=_elapsed(),
                executor_stdout_tail=stdout_tail,
                executor_stderr_tail=stderr_tail,
                executor_log_path=log_path,
                declared_transient_paths=prompt.transient_paths,
            )

        # Controlled transient cleanup (opt-in) BEFORE normal postconditions.
        t_observed: tuple[str, ...] = ()
        t_cleaned: tuple[str, ...] = ()
        t_verified: Optional[bool] = None
        t_sha: Optional[dict] = None
        if prompt.transient_paths:
            cleanup = classify_and_cleanup_transients(
                prompt_allowed=prompt.allowed_paths,
                prompt_transient=prompt.transient_paths,
                baselines=baselines,
                executor_worktree=executor_worktree,
                git_runner=runner,
            )
            t_observed = cleanup.observed
            t_cleaned = cleanup.cleaned
            t_verified = cleanup.cleanup_verified
            t_sha = cleanup.sha256_by_path or None
            messages.append(f"transient: {cleanup.reason}")
            if not cleanup.ok:
                decision = Decision(
                    action=Action.LAUNCH_EXECUTOR,
                    state=CoordState.HUMAN_REQUIRED,
                    reason=cleanup.reason,
                    would_launch=True,
                    mutations=("claim", "launch_executor"),
                    safety=decision.safety,
                )
                return RunResult(
                    mode=mode,
                    decision=decision,
                    executor_launched=True,
                    executor_exit_code=exit_code,
                    messages=tuple(messages),
                    final_status=cleanup.final_status,
                    postconditions_ok=False,
                    unexpected_paths=cleanup.remaining_unexpected,
                    elapsed_seconds=_elapsed(),
                    executor_stdout_tail=stdout_tail,
                    executor_stderr_tail=stderr_tail,
                    executor_log_path=log_path,
                    declared_transient_paths=prompt.transient_paths,
                    transient_paths_observed=t_observed,
                    transient_paths_cleaned=t_cleaned,
                    transient_cleanup_verified=t_verified,
                    transient_sha256=t_sha,
                )

        post = evaluate_postconditions(
            prompt,
            executor_worktree=executor_worktree,
            git_runner=runner,
        )
        post_ok = post.ok
        unexpected = post.unexpected_paths
        required_ok = post.required_paths_ok
        validation_ok = post.validation_ok
        messages.append(f"postconditions: {post.reason}")

        if not post.ok:
            final_status = post.final_status
            decision = Decision(
                action=Action.LAUNCH_EXECUTOR,
                state=CoordState.HUMAN_REQUIRED,
                reason=post.reason,
                would_launch=True,
                mutations=("claim", "launch_executor"),
                safety=decision.safety,
            )
            return RunResult(
                mode=mode,
                decision=decision,
                executor_launched=True,
                executor_exit_code=exit_code,
                messages=tuple(messages),
                final_status=final_status,
                postconditions_ok=False,
                unexpected_paths=unexpected,
                required_paths_ok=required_ok,
                validation_ok=validation_ok,
                elapsed_seconds=_elapsed(),
                executor_stdout_tail=stdout_tail,
                executor_stderr_tail=stderr_tail,
                executor_log_path=log_path,
                declared_transient_paths=prompt.transient_paths,
                transient_paths_observed=t_observed,
                transient_paths_cleaned=t_cleaned,
                transient_cleanup_verified=t_verified,
                transient_sha256=t_sha,
            )

        pub = publish_exact_paths(
            prompt,
            executor_worktree=executor_worktree,
            paths_to_stage=post.changed_paths,
            git_runner=runner,
        )
        commit_created = pub.commit_created
        local_head = pub.local_head
        push_attempted = pub.push_attempted
        remote_head = pub.remote_head
        publication_verified = pub.publication_verified
        final_status = pub.final_status
        messages.append(f"publication: {pub.reason}")
        if pub.git_commands:
            messages.append(
                "git_commands="
                + "; ".join(" ".join(c) for c in pub.git_commands)
            )

        end_state = CoordState.EXECUTOR_READY
        if final_status != FinalStatus.WORK_PACKAGE_SUCCESS:
            end_state = CoordState.HUMAN_REQUIRED

        decision = Decision(
            action=Action.LAUNCH_EXECUTOR,
            state=end_state,
            reason=pub.reason,
            would_launch=True,
            mutations=("claim", "launch_executor", "publication"),
            safety=decision.safety,
        )
        return RunResult(
            mode=mode,
            decision=decision,
            executor_launched=True,
            executor_exit_code=exit_code,
            messages=tuple(messages),
            final_status=final_status,
            postconditions_ok=True,
            unexpected_paths=(),
            required_paths_ok=True,
            validation_ok=True,
            commit_created=commit_created,
            local_head=local_head,
            push_attempted=push_attempted,
            remote_head=remote_head,
            publication_verified=publication_verified,
            elapsed_seconds=_elapsed(),
            executor_stdout_tail=stdout_tail,
            executor_stderr_tail=stderr_tail,
            executor_log_path=log_path,
            declared_transient_paths=prompt.transient_paths,
            transient_paths_observed=t_observed,
            transient_paths_cleaned=t_cleaned,
            transient_cleanup_verified=t_verified,
            transient_sha256=t_sha,
        )
    finally:
        lock.release()


def result_to_json(result: RunResult) -> dict:
    return {
        "mode": result.mode,
        "action": result.decision.action.value,
        "state": result.decision.state.value if result.decision.state else None,
        "reason": result.decision.reason,
        "would_launch": result.decision.would_launch,
        "mutations": list(result.decision.mutations),
        "executor_launched": result.executor_launched,
        "executor_exit_code": result.executor_exit_code,
        "postconditions_ok": result.postconditions_ok,
        "unexpected_paths": list(result.unexpected_paths),
        "required_paths_ok": result.required_paths_ok,
        "validation_ok": result.validation_ok,
        "commit_created": result.commit_created,
        "local_head": result.local_head,
        "push_attempted": result.push_attempted,
        "remote_head": result.remote_head,
        "publication_verified": result.publication_verified,
        "final_status": result.final_status.value,
        "elapsed_seconds": result.elapsed_seconds,
        "executor_stdout_tail": result.executor_stdout_tail,
        "executor_stderr_tail": result.executor_stderr_tail,
        "executor_log_path": result.executor_log_path,
        "declared_transient_paths": list(result.declared_transient_paths),
        "transient_paths_observed": list(result.transient_paths_observed),
        "transient_paths_cleaned": list(result.transient_paths_cleaned),
        "transient_cleanup_verified": result.transient_cleanup_verified,
        "transient_sha256": result.transient_sha256,
        "messages": list(result.messages),
        "safety_ok": (
            None if result.decision.safety is None else result.decision.safety.ok
        ),
        "safety_reasons": (
            []
            if result.decision.safety is None
            else list(result.decision.safety.reasons)
        ),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = (args.repo_root or Path.cwd()).resolve()
    executor_worktree = (args.executor_worktree or repo_root).resolve()
    bridge_worktree = (
        args.bridge_worktree.resolve() if args.bridge_worktree is not None else None
    )

    if args.bridge_prompt is not None:
        bridge_path = args.bridge_prompt.resolve()
    elif bridge_worktree is not None:
        bridge_path = (bridge_worktree / DEFAULT_BRIDGE_REL).resolve()
    else:
        bridge_path = (repo_root / DEFAULT_BRIDGE_REL).resolve()

    state_dir = args.state_dir.resolve() if args.state_dir else None

    result = run_once(
        mode=args.mode,
        repo_root=repo_root,
        executor_worktree=executor_worktree,
        bridge_prompt_path=bridge_path,
        bridge_worktree=bridge_worktree,
        agent_bin=args.agent_bin,
        allow_dirty=args.allow_dirty,
        state_dir=state_dir,
    )

    if args.json:
        print(json.dumps(result_to_json(result), ensure_ascii=False, indent=2))
    else:
        for line in result.messages:
            print(line)
        print(
            f"RESULT mode={result.mode} final_status={result.final_status.value} "
            f"launched={result.executor_launched} "
            f"commit={result.commit_created} push={result.push_attempted}"
        )

    if result.final_status == FinalStatus.WORK_PACKAGE_SUCCESS:
        return 0
    if result.final_status in (
        FinalStatus.SHADOW_OK,
        FinalStatus.WAIT_OK,
    ):
        return 0
    if result.final_status == FinalStatus.EXECUTOR_PROCESS_EXITED_ZERO:
        # Не полный success — exit 3 чтобы не путать с WORK_PACKAGE_SUCCESS.
        return 3
    if result.decision.action == Action.FAIL_CLOSED:
        return 2
    if result.final_status in (
        FinalStatus.HUMAN_REQUIRED,
        FinalStatus.POSTCONDITION_FAILED,
        FinalStatus.VALIDATION_FAILED,
        FinalStatus.PUBLICATION_FAILED,
        FinalStatus.PUBLICATION_UNVERIFIED,
        FinalStatus.EXECUTOR_NONZERO,
    ):
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
