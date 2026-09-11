"""CLI Coordinator v0.1.1: --mode shadow|launch --once + claim/lock/bridge."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from tools.dev_coordinator.claim import try_acquire_claim
from tools.dev_coordinator.decision import decide
from tools.dev_coordinator.executor import (
    compose_executor_prompt,
    launch_executor_once,
)
from tools.dev_coordinator.locks import ProcessLock
from tools.dev_coordinator.models import Action, CoordState, Decision, RunResult
from tools.dev_coordinator.parse import parse_next_prompt
from tools.dev_coordinator.paths import default_state_dir
from tools.dev_coordinator.safety import (
    GitRunner,
    _default_git_runner,
    verify_bridge_source,
)


DEFAULT_BRIDGE_REL = Path("docs/agent-bridge/next-prompt.md")


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_executor_governance(executor_worktree: Path) -> str:
    """Authoritative governance из exact executor worktree (не stale primary)."""
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dev_coordinator",
        description=(
            "Deterministic Coordinator v0.1.1 over docs/agent-bridge. "
            "Default mode is shadow (no mutations)."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("shadow", "launch"),
        default="shadow",
        help="shadow=report only (default); launch=may start Cursor once",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        default=True,
        help="Evaluate once and exit (default; endless loops not implemented)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Primary AI Core checkout (default: cwd). Not silently switched.",
    )
    parser.add_argument(
        "--executor-worktree",
        type=Path,
        default=None,
        help="Worktree where Executor may run (defaults to --repo-root)",
    )
    parser.add_argument(
        "--bridge-worktree",
        type=Path,
        default=None,
        help="Git worktree that owns the active agent-bridge (required for launch)",
    )
    parser.add_argument(
        "--bridge-prompt",
        type=Path,
        default=None,
        help=(
            "Path to next-prompt.md "
            "(default: <bridge-worktree or repo>/docs/agent-bridge/next-prompt.md)"
        ),
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="Override Coordinator state dir (claims/locks); default XDG state",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON result",
    )
    parser.add_argument(
        "--agent-bin",
        default="agent",
        help="Cursor Agent CLI binary (default: agent)",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="DEBUG/shadow only; launch+allow-dirty fails closed in v0.1.1",
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
    """Одна оценка (+ опциональный launch с claim/lock)."""
    messages: list[str] = []
    runner = git_runner or _default_git_runner
    state = (state_dir or default_state_dir()).resolve()

    if not bridge_prompt_path.is_file():
        decision = Decision(
            action=Action.FAIL_CLOSED,
            state=CoordState.HUMAN_REQUIRED,
            reason=f"bridge prompt not found: {bridge_prompt_path}",
            would_launch=False,
            mutations=(),
        )
        return RunResult(
            mode=mode,
            decision=decision,
            executor_launched=False,
            executor_exit_code=None,
            messages=(decision.reason,),
        )

    # launch требует явный bridge-worktree.
    if mode == "launch" and bridge_worktree is None:
        decision = Decision(
            action=Action.FAIL_CLOSED,
            state=CoordState.HUMAN_REQUIRED,
            reason="--bridge-worktree is required for launch mode in v0.1.1",
            would_launch=False,
            mutations=(),
        )
        return RunResult(
            mode=mode,
            decision=decision,
            executor_launched=False,
            executor_exit_code=None,
            messages=(decision.reason,),
        )

    text = _load_text(bridge_prompt_path)
    prompt = parse_next_prompt(text)
    messages.append(
        f"parsed has_metadata={prompt.has_metadata} state={prompt.state} "
        f"parse_error={prompt.parse_error!r}"
    )

    # Bridge source verification (когда worktree задан).
    if bridge_worktree is not None:
        expected_repo = prompt.target_repo if prompt.has_metadata else "kkobanenko/ai-core"
        # Для legacy WAIT expected_repo по умолчанию ai-core.
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
                return RunResult(
                    mode=mode,
                    decision=decision,
                    executor_launched=False,
                    executor_exit_code=None,
                    messages=tuple(messages + [decision.reason]),
                )
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

    executor_launched = False
    exit_code: Optional[int] = None

    if not (
        launch
        and mode == "launch"
        and decision.action == Action.LAUNCH_EXECUTOR
        and decision.would_launch
    ):
        return RunResult(
            mode=mode,
            decision=decision,
            executor_launched=False,
            executor_exit_code=None,
            messages=tuple(messages),
        )

    # --- Live launch path: process lock → claim → fake/real executor ---
    lock = ProcessLock(state_dir=state, non_blocking=True)
    if not lock.acquire():
        decision = Decision(
            action=Action.NONE,
            state=CoordState.HUMAN_REQUIRED,
            reason="another Coordinator holds the process lock; refusing launch",
            would_launch=False,
            mutations=(),
        )
        messages.append(decision.reason)
        return RunResult(
            mode=mode,
            decision=decision,
            executor_launched=False,
            executor_exit_code=None,
            messages=tuple(messages),
        )

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
            )

        # Governance только из executor_worktree.
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
        messages.append(f"executor exit_code={exit_code}")
        messages.append("Coordinator stop after single executor observation")
        decision = Decision(
            action=Action.LAUNCH_EXECUTOR,
            state=CoordState.EXECUTOR_READY,
            reason="claimed and launched executor once; claim persists",
            would_launch=True,
            mutations=("claim", "launch_executor"),
            safety=decision.safety,
        )
    finally:
        lock.release()

    return RunResult(
        mode=mode,
        decision=decision,
        executor_launched=executor_launched,
        executor_exit_code=exit_code,
        messages=tuple(messages),
    )


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
        payload = {
            "mode": result.mode,
            "action": result.decision.action.value,
            "state": result.decision.state.value if result.decision.state else None,
            "reason": result.decision.reason,
            "would_launch": result.decision.would_launch,
            "mutations": list(result.decision.mutations),
            "executor_launched": result.executor_launched,
            "executor_exit_code": result.executor_exit_code,
            "messages": list(result.messages),
            "safety_ok": (
                None
                if result.decision.safety is None
                else result.decision.safety.ok
            ),
            "safety_reasons": (
                []
                if result.decision.safety is None
                else list(result.decision.safety.reasons)
            ),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for line in result.messages:
            print(line)
        print(
            f"RESULT mode={result.mode} action={result.decision.action.value} "
            f"would_launch={result.decision.would_launch} "
            f"launched={result.executor_launched}"
        )

    if result.decision.action == Action.FAIL_CLOSED:
        return 2
    if result.decision.state and result.decision.state.value == "HUMAN_REQUIRED":
        return 2
    if result.executor_launched and result.executor_exit_code not in (0, None):
        return result.executor_exit_code or 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
