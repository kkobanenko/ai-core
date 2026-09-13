"""Сборка промпта и запуск Cursor Agent CLI (ровно один раз) — v0.2."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from tools.dev_coordinator.models import BridgePrompt

ExecutorRunner = Callable[[Sequence[str], Path], tuple[int, str, str]]

OUTPUT_TAIL_BYTES = 32 * 1024


PRESERVE_BRIDGE_INSTRUCTION = """
## Coordinator v0.2 — Executor responsibilities

You are the Cursor Executor launched by the deterministic Coordinator.

### You MUST
1. Treat the Architect `next-prompt.md` body as the active instruction.
2. Change only paths allowed by Architect (and Coordinator metadata).
3. Create required report/artifact files when asked.
4. Run available local checks that do not require git commit/push.
5. Finish when implementation/report work is done.

### You MUST NOT (Coordinator owns these)
1. `git commit`
2. `git push`
3. Create pull requests
4. Create/delete/rename remote branches
5. Trigger hosted CI / workflow_dispatch
6. Force-push or touch `main`

If shell/git tools are unavailable or rejected: still write the allowed files
you can create with your edit tools, then exit. The Coordinator will inspect
the real worktree (`git status`) and perform exact-path commit/push itself.

### Reporting
Do not rely on updating `docs/agent-bridge/**` unless the Architect prompt
explicitly requires it. Prefer the artifact path declared in the prompt.

Repository governance (`AGENTS.md`, `.cursor/rules/**`, platform-control) wins
on conflicts with bridge text.
""".strip()


def compose_executor_prompt(
    *,
    governance_text: str,
    bridge_prompt: BridgePrompt,
    coordinator_note: str = "",
) -> str:
    """Собрать промпт Executor без переинтерпретации требований Architect."""
    parts = [
        "# Repository governance (from executor_worktree)\n\n"
        + governance_text.strip(),
    ]
    if coordinator_note.strip():
        parts.append(
            "# Coordinator tooling note (non-authoritative)\n\n"
            + coordinator_note.strip()
        )
    if bridge_prompt.allowed_paths:
        parts.append(
            "# Allowed paths (Coordinator metadata)\n\n"
            + "\n".join(f"- {p}" for p in bridge_prompt.allowed_paths)
        )
    if bridge_prompt.required_paths:
        parts.append(
            "# Required artifacts (Coordinator metadata)\n\n"
            + "\n".join(f"- {p}" for p in bridge_prompt.required_paths)
        )
    parts.append(
        "# Active next-prompt.md (full)\n\n" + bridge_prompt.raw_text.strip()
    )
    parts.append(PRESERVE_BRIDGE_INSTRUCTION)
    return "\n\n---\n\n".join(parts) + "\n"


def tail_text(text: str, max_bytes: int = OUTPUT_TAIL_BYTES) -> str:
    """Хвост текста ≤ max_bytes (UTF-8 safe truncation)."""
    raw = (text or "").encode("utf-8")
    if len(raw) <= max_bytes:
        return text or ""
    chunk = raw[-max_bytes:]
    # Обрезать возможный битый leading UTF-8 символ.
    return chunk.decode("utf-8", errors="ignore")


def _default_runner(args: Sequence[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        list(args),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


@dataclass(frozen=True)
class LaunchOutcome:
    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str


def build_agent_argv(
    *,
    prompt_text: str,
    workspace: Path,
    agent_bin: str = "agent",
    trust: bool = True,
) -> list[str]:
    argv = [agent_bin, "--print", "--workspace", str(workspace)]
    if trust:
        argv.append("--trust")
    argv.append(prompt_text)
    return argv


def launch_executor_once(
    *,
    prompt_text: str,
    workspace: Path,
    agent_bin: str = "agent",
    trust: bool = True,
    runner: Optional[ExecutorRunner] = None,
) -> LaunchOutcome:
    """Запустить Cursor Executor ровно один раз."""
    run = runner or _default_runner
    argv = build_agent_argv(
        prompt_text=prompt_text,
        workspace=workspace,
        agent_bin=agent_bin,
        trust=trust,
    )
    code, out, err = run(argv, workspace)
    return LaunchOutcome(
        argv=tuple(argv),
        exit_code=code,
        stdout=out,
        stderr=err,
    )
