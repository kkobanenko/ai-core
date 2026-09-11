"""CLI Coordinator v0.1: --mode shadow|launch --once."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from tools.dev_coordinator.decision import decide
from tools.dev_coordinator.executor import (
    compose_executor_prompt,
    launch_executor_once,
)
from tools.dev_coordinator.models import Action, RunResult
from tools.dev_coordinator.parse import parse_next_prompt


DEFAULT_BRIDGE_PROMPT = Path("docs/agent-bridge/next-prompt.md")


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_governance(repo_root: Path) -> str:
    """Собрать краткий governance-контекст для Executor."""
    chunks: list[str] = []
    agents = repo_root / "AGENTS.md"
    if agents.is_file():
        chunks.append(agents.read_text(encoding="utf-8"))
    rules_dir = repo_root / ".cursor" / "rules"
    if rules_dir.is_dir():
        for path in sorted(rules_dir.glob("**/*")):
            if path.is_file() and path.suffix in {".md", ".mdc", ".txt"}:
                chunks.append(
                    f"## {path.relative_to(repo_root)}\n\n"
                    + path.read_text(encoding="utf-8")
                )
    if not chunks:
        return "(no AGENTS.md / .cursor/rules found)"
    return "\n\n".join(chunks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dev_coordinator",
        description=(
            "Deterministic Coordinator v0.1 over docs/agent-bridge. "
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
        "--bridge-prompt",
        type=Path,
        default=None,
        help="Path to next-prompt.md (default: <repo>/docs/agent-bridge/next-prompt.md)",
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
        help="Allow launch with dirty worktree (dangerous; tests/debug only)",
    )
    return parser


def run_once(
    *,
    mode: str,
    repo_root: Path,
    executor_worktree: Path,
    bridge_prompt_path: Path,
    agent_bin: str = "agent",
    allow_dirty: bool = False,
    launch: bool = True,
) -> RunResult:
    """Одна оценка (+ опциональный launch). Без сетевых побочных эффектов в shadow."""
    messages: list[str] = []

    if not bridge_prompt_path.is_file():
        # Отсутствие bridge-файла — fail closed (нужен человек).
        from tools.dev_coordinator.models import Action as A
        from tools.dev_coordinator.models import CoordState, Decision

        decision = Decision(
            action=A.FAIL_CLOSED,
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

    text = _load_text(bridge_prompt_path)
    prompt = parse_next_prompt(text)
    messages.append(
        f"parsed has_metadata={prompt.has_metadata} state={prompt.state} "
        f"parse_error={prompt.parse_error!r}"
    )

    decision = decide(
        prompt,
        mode=mode,
        primary_repo=repo_root,
        executor_worktree=executor_worktree,
        allow_dirty=allow_dirty,
    )
    messages.append(f"decision action={decision.action.value} reason={decision.reason}")

    executor_launched = False
    exit_code: Optional[int] = None

    if (
        launch
        and mode == "launch"
        and decision.action == Action.LAUNCH_EXECUTOR
        and decision.would_launch
    ):
        governance = _load_governance(repo_root)
        composed = compose_executor_prompt(
            governance_text=governance,
            bridge_prompt=prompt,
        )
        outcome = launch_executor_once(
            prompt_text=composed,
            workspace=executor_worktree,
            agent_bin=agent_bin,
        )
        executor_launched = True
        exit_code = outcome.exit_code
        messages.append(f"executor exit_code={exit_code}")
        # После запуска Coordinator v0.1 останавливается (без цикла).
        messages.append("Coordinator stop after single executor observation")

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
    bridge_path = (
        args.bridge_prompt
        if args.bridge_prompt is not None
        else repo_root / DEFAULT_BRIDGE_PROMPT
    )

    result = run_once(
        mode=args.mode,
        repo_root=repo_root,
        executor_worktree=executor_worktree,
        bridge_prompt_path=bridge_path,
        agent_bin=args.agent_bin,
        allow_dirty=args.allow_dirty,
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

    # Exit codes: 0 = clean stop (включая WAIT / shadow);
    # 2 = fail closed / human required.
    if result.decision.action == Action.FAIL_CLOSED:
        return 2
    if result.decision.state and result.decision.state.value == "HUMAN_REQUIRED":
        return 2
    if result.executor_launched and result.executor_exit_code not in (0, None):
        return result.executor_exit_code or 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
