"""Сборка промпта и запуск Cursor Agent CLI (ровно один раз)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from tools.dev_coordinator.models import BridgePrompt

# Подмена subprocess в тестах.
ExecutorRunner = Callable[[Sequence[str], Path], tuple[int, str, str]]


PRESERVE_BRIDGE_INSTRUCTION = """
## Coordinator v0.1.1 — preserve legacy agent-bridge workflow

You are the Cursor Executor launched by the deterministic Coordinator.

Preserve the existing Architect ↔ docs/agent-bridge/** ↔ Executor convention:

1. Treat `docs/agent-bridge/next-prompt.md` as the active instruction.
2. Do not reinterpret Architect requirements; follow them literally.
3. After work, update `docs/agent-bridge/latest-report.md` and archive under
   `docs/agent-bridge/reports/` / `docs/agent-bridge/prompts/` as usual.
4. Do not create hosted CI workflows, PRs for CI, or workflow_dispatch.
5. Coordinator does not take over commit/push/report publication in v0.1 —
   continue the existing Executor ownership for those steps unless the prompt
   says otherwise.

Repository governance (`AGENTS.md`, `.cursor/rules/**`, platform-control) wins
over bridge text on conflicts; record conflicts in the report.
""".strip()


def compose_executor_prompt(
    *,
    governance_text: str,
    bridge_prompt: BridgePrompt,
    coordinator_note: str = "",
) -> str:
    """Собрать промпт Executor без переинтерпретации требований Architect.

    governance_text должен быть из executor_worktree (authoritative).
    coordinator_note — опциональный явный блок transition tooling, не governance.
    """
    parts = [
        "# Repository governance (from executor_worktree)\n\n"
        + governance_text.strip(),
    ]
    if coordinator_note.strip():
        parts.append(
            "# Coordinator tooling note (non-authoritative)\n\n"
            + coordinator_note.strip()
        )
    parts.append(
        "# Active next-prompt.md (full)\n\n" + bridge_prompt.raw_text.strip()
    )
    parts.append(PRESERVE_BRIDGE_INSTRUCTION)
    return "\n\n---\n\n".join(parts) + "\n"


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
    """Результат одного запуска agent CLI."""

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
    """Собрать argv для Cursor headless CLI.

    Проверено локально: `agent -p/--print` печатает ответ и имеет доступ к tools.
    Промпт передаётся позиционным аргументом. Не выдумываем неизвестные флаги.
    """
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
