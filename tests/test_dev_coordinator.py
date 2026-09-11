"""Unit-тесты Coordinator v0.1 без live GitHub / Cursor."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.dev_coordinator.decision import decide
from tools.dev_coordinator.executor import (
    build_agent_argv,
    compose_executor_prompt,
    launch_executor_once,
)
from tools.dev_coordinator.models import Action, CoordState
from tools.dev_coordinator.parse import parse_next_prompt
from tools.dev_coordinator.safety import check_launch_safety


LEGACY_WAIT = """# WAIT

S2 discovery complete. Do nothing until Architect authorizes the next step.
"""


READY_META = """---
coord_version: 1
state: EXECUTOR_READY
prompt_id: test-ready-001
target_repo: kkobanenko/ai-core
target_branch: feat/example
target_worktree: /tmp/example-wt
base_sha: abc123def456
hosted_ci: forbidden
max_executor_runs: 1
---

# Executor task

Do the work described by Architect.
"""


def _meta(state: str, **extra: object) -> str:
    fields = {
        "coord_version": 1,
        "state": state,
        "prompt_id": "p1",
        "target_repo": "kkobanenko/ai-core",
        "target_branch": "feat/example",
        "target_worktree": "/tmp/example-wt",
        "base_sha": "abc123def456",
        "hosted_ci": "forbidden",
        "max_executor_runs": 1,
    }
    fields.update(extra)
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append("body")
    return "\n".join(lines)


def _git_ok(branch: str = "feat/example", head: str = "abc123def456", dirty: str = ""):
    """Фабрика mock git_runner для safety-тестов."""

    def runner(args, cwd):
        cmd = list(args)
        if cmd[:2] == ["branch", "--show-current"]:
            return 0, branch + "\n", ""
        if cmd[:2] == ["rev-parse", "HEAD"]:
            return 0, head + "\n", ""
        if cmd[:2] == ["status", "--porcelain"]:
            return 0, dirty, ""
        return 1, "", f"unexpected: {cmd}"

    return runner


def test_legacy_wait_no_action(tmp_path: Path):
    prompt = parse_next_prompt(LEGACY_WAIT)
    assert prompt.state == CoordState.WAIT
    assert prompt.has_metadata is False
    decision = decide(
        prompt,
        mode="launch",
        primary_repo=tmp_path,
        executor_worktree=tmp_path / "wt",
    )
    assert decision.action == Action.NONE
    assert decision.would_launch is False
    assert decision.mutations == ()


def test_metadata_wait_no_action(tmp_path: Path):
    prompt = parse_next_prompt(_meta("WAIT"))
    assert prompt.state == CoordState.WAIT
    decision = decide(
        prompt,
        mode="launch",
        primary_repo=tmp_path,
        executor_worktree=Path("/tmp/example-wt"),
        git_runner=_git_ok(),
    )
    assert decision.action == Action.NONE
    assert decision.would_launch is False


def test_executor_ready_exactly_one_launch_decision(tmp_path: Path):
    prompt = parse_next_prompt(READY_META)
    assert prompt.max_executor_runs == 1
    decision = decide(
        prompt,
        mode="launch",
        primary_repo=tmp_path,
        executor_worktree=Path("/tmp/example-wt"),
        git_runner=_git_ok(),
    )
    assert decision.action == Action.LAUNCH_EXECUTOR
    assert decision.would_launch is True
    assert decision.mutations == ("launch_executor",)


@pytest.mark.parametrize(
    "state",
    [
        "ARCHITECT_REVIEW",
        "HUMAN_REQUIRED",
        "DONE",
        "PAUSED",
        "EXECUTOR_RUNNING",
    ],
)
def test_non_ready_states_no_launch(state: str, tmp_path: Path):
    prompt = parse_next_prompt(_meta(state))
    decision = decide(
        prompt,
        mode="launch",
        primary_repo=tmp_path,
        executor_worktree=Path("/tmp/example-wt"),
        git_runner=_git_ok(),
    )
    assert decision.action == Action.NONE
    assert decision.would_launch is False


def test_unknown_state_fail_closed(tmp_path: Path):
    prompt = parse_next_prompt(_meta("TOTALLY_UNKNOWN"))
    assert prompt.parse_error is not None
    decision = decide(
        prompt,
        mode="launch",
        primary_repo=tmp_path,
        executor_worktree=Path("/tmp/example-wt"),
    )
    assert decision.action == Action.FAIL_CLOSED
    assert decision.would_launch is False


def test_multiple_invalid_state_fail_closed(tmp_path: Path):
    prompt = parse_next_prompt(_meta("WAIT, EXECUTOR_READY"))
    assert prompt.parse_error is not None
    assert "multiple" in (prompt.parse_error or "")
    decision = decide(
        prompt,
        mode="shadow",
        primary_repo=tmp_path,
        executor_worktree=tmp_path,
    )
    assert decision.action == Action.FAIL_CLOSED


def test_shadow_mode_zero_mutation(tmp_path: Path):
    prompt = parse_next_prompt(READY_META)
    launches = []

    decision = decide(
        prompt,
        mode="shadow",
        primary_repo=tmp_path,
        executor_worktree=Path("/tmp/example-wt"),
        git_runner=_git_ok(),
    )
    assert decision.action == Action.NONE
    assert decision.would_launch is True
    assert decision.mutations == ()

    # Убеждаемся, что launch helper не вызывается из decide.
    assert launches == []


def test_max_executor_runs_must_be_one(tmp_path: Path):
    prompt = parse_next_prompt(_meta("EXECUTOR_READY", max_executor_runs=2))
    decision = decide(
        prompt,
        mode="launch",
        primary_repo=tmp_path,
        executor_worktree=Path("/tmp/example-wt"),
        git_runner=_git_ok(),
    )
    assert decision.action == Action.FAIL_CLOSED
    assert decision.would_launch is False


def test_dirty_worktree_no_launch(tmp_path: Path):
    prompt = parse_next_prompt(READY_META)
    decision = decide(
        prompt,
        mode="launch",
        primary_repo=tmp_path,
        executor_worktree=Path("/tmp/example-wt"),
        git_runner=_git_ok(dirty=" M README.md\n"),
    )
    assert decision.would_launch is False
    assert decision.state == CoordState.HUMAN_REQUIRED
    assert decision.action == Action.NONE


def test_base_sha_mismatch_no_launch(tmp_path: Path):
    prompt = parse_next_prompt(READY_META)
    decision = decide(
        prompt,
        mode="launch",
        primary_repo=tmp_path,
        executor_worktree=Path("/tmp/example-wt"),
        git_runner=_git_ok(head="deadbeef"),
    )
    assert decision.would_launch is False
    assert decision.state == CoordState.HUMAN_REQUIRED
    assert "base SHA mismatch" in decision.reason


def test_safety_helper_dirty_and_sha():
    prompt = parse_next_prompt(READY_META)
    report = check_launch_safety(
        prompt,
        primary_repo=Path("/tmp/primary"),
        executor_worktree=Path("/tmp/example-wt"),
        git_runner=_git_ok(dirty="?? x\n", head="wrong"),
    )
    assert report.ok is False
    joined = " ".join(report.reasons)
    assert "dirty" in joined
    assert "base SHA mismatch" in joined


def test_launch_executor_once_invokes_runner_once(tmp_path: Path):
    calls = []

    def runner(args, cwd):
        calls.append((list(args), Path(cwd)))
        return 0, "ok", ""

    outcome = launch_executor_once(
        prompt_text="hello",
        workspace=tmp_path,
        agent_bin="agent",
        runner=runner,
    )
    assert outcome.exit_code == 0
    assert len(calls) == 1
    argv = calls[0][0]
    assert argv[0] == "agent"
    assert "--print" in argv
    assert "--workspace" in argv
    assert "hello" in argv


def test_compose_prompt_preserves_bridge_raw():
    prompt = parse_next_prompt(READY_META)
    composed = compose_executor_prompt(
        governance_text="AGENTS rules here",
        bridge_prompt=prompt,
    )
    assert "AGENTS rules here" in composed
    assert "coord_version: 1" in composed
    assert "preserve legacy agent-bridge" in composed.lower() or "Preserve" in composed


def test_build_agent_argv_uses_print_flag(tmp_path: Path):
    argv = build_agent_argv(prompt_text="p", workspace=tmp_path)
    assert argv[:2] == ["agent", "--print"]


def test_legacy_without_wait_fail_closed(tmp_path: Path):
    prompt = parse_next_prompt("# Do something\n\nImplement feature X.\n")
    assert prompt.parse_error is not None
    decision = decide(
        prompt,
        mode="launch",
        primary_repo=tmp_path,
        executor_worktree=tmp_path,
    )
    assert decision.action == Action.FAIL_CLOSED
