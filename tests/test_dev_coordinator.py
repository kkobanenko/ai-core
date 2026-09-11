"""Unit/integration тесты Coordinator v0.1.1 без live GitHub / Cursor."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

import pytest

from tools.dev_coordinator.claim import try_acquire_claim
from tools.dev_coordinator.cli import load_executor_governance, run_once
from tools.dev_coordinator.decision import decide
from tools.dev_coordinator.executor import (
    build_agent_argv,
    compose_executor_prompt,
    launch_executor_once,
)
from tools.dev_coordinator.gitutil import canonicalize_github_repo
from tools.dev_coordinator.locks import ProcessLock
from tools.dev_coordinator.models import Action, CoordState
from tools.dev_coordinator.parse import parse_next_prompt
from tools.dev_coordinator.safety import check_launch_safety, verify_bridge_source


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
    # Удаляем ключи со значением object() sentinel? Используем None для удаления.
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            continue
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append("body")
    return "\n".join(lines)


def _git_ok(
    branch: str = "feat/example",
    head: str = "abc123def456",
    dirty: str = "",
    origin: str = "git@github.com:kkobanenko/ai-core.git",
    remote_tip: Optional[str] = "abc123def456",
    bridge_branch: str = "test/bridge",
    bridge_head: str = "bridgehead001",
):
    """Фабрика mock git_runner для safety/bridge тестов."""

    def runner(args, cwd):
        cmd = list(args)
        cwd_s = str(cwd)
        if cmd[:2] == ["branch", "--show-current"]:
            if "bridge" in cwd_s:
                return 0, bridge_branch + "\n", ""
            return 0, branch + "\n", ""
        if cmd[:2] == ["rev-parse", "HEAD"]:
            if "bridge" in cwd_s:
                return 0, bridge_head + "\n", ""
            return 0, head + "\n", ""
        if cmd == ["rev-parse", "--is-inside-work-tree"]:
            return 0, "true\n", ""
        if cmd[:2] == ["status", "--porcelain"]:
            return 0, dirty, ""
        if cmd[:3] == ["remote", "get-url", "origin"]:
            return 0, origin + "\n", ""
        if cmd[:2] == ["ls-remote", "origin"]:
            tip = remote_tip if "bridge" not in cwd_s else bridge_head
            if tip is None:
                return 1, "", "network fail"
            ref = cmd[2] if len(cmd) > 2 else "refs/heads/x"
            return 0, f"{tip}\t{ref}\n", ""
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
    # Короткий metadata для WAIT допустим.
    text = "---\ncoord_version: 1\nstate: WAIT\n---\n\n# WAIT\n"
    prompt = parse_next_prompt(text)
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
    text = f"---\ncoord_version: 1\nstate: {state}\n---\n\nbody\n"
    prompt = parse_next_prompt(text)
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


def test_duplicate_metadata_keys_fail_closed():
    text = """---
coord_version: 1
state: WAIT
state: EXECUTOR_READY
---

body
"""
    prompt = parse_next_prompt(text)
    assert prompt.parse_error is not None
    assert "duplicate" in prompt.parse_error


def test_executor_ready_missing_field_fail_closed():
    text = """---
coord_version: 1
state: EXECUTOR_READY
prompt_id: x
target_repo: kkobanenko/ai-core
target_branch: feat/x
base_sha: abc
hosted_ci: forbidden
max_executor_runs: 1
---

# missing target_worktree
"""
    prompt = parse_next_prompt(text)
    assert prompt.parse_error is not None
    assert "target_worktree" in prompt.parse_error


def test_executor_ready_empty_prompt_id_fail_closed():
    prompt = parse_next_prompt(_meta("EXECUTOR_READY", prompt_id=""))
    assert prompt.parse_error is not None


def test_shadow_mode_zero_mutation(tmp_path: Path):
    prompt = parse_next_prompt(READY_META)
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


def test_launch_plus_allow_dirty_fail_closed(tmp_path: Path):
    prompt = parse_next_prompt(READY_META)
    decision = decide(
        prompt,
        mode="launch",
        primary_repo=tmp_path,
        executor_worktree=Path("/tmp/example-wt"),
        git_runner=_git_ok(),
        allow_dirty=True,
    )
    assert decision.action == Action.FAIL_CLOSED
    assert decision.would_launch is False


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


def test_target_repo_mismatch_no_launch(tmp_path: Path):
    prompt = parse_next_prompt(READY_META)
    decision = decide(
        prompt,
        mode="launch",
        primary_repo=tmp_path,
        executor_worktree=Path("/tmp/example-wt"),
        git_runner=_git_ok(origin="git@github.com:other/repo.git"),
    )
    assert decision.would_launch is False
    assert "target_repo mismatch" in decision.reason


@pytest.mark.parametrize(
    "url,expected",
    [
        ("git@github.com:kkobanenko/ai-core.git", "kkobanenko/ai-core"),
        ("https://github.com/kkobanenko/ai-core.git", "kkobanenko/ai-core"),
        ("https://github.com/kkobanenko/ai-core", "kkobanenko/ai-core"),
        ("ssh://git@github.com/kkobanenko/ai-core.git", "kkobanenko/ai-core"),
    ],
)
def test_canonicalize_github_repo(url: str, expected: str):
    assert canonicalize_github_repo(url) == expected


def test_claim_exactly_once(tmp_path: Path):
    state = tmp_path / "state"
    prompt = parse_next_prompt(READY_META)
    first = try_acquire_claim(prompt, state_dir=state)
    second = try_acquire_claim(prompt, state_dir=state)
    assert first.acquired is True
    assert second.acquired is False
    assert "already exists" in second.reason


def test_process_lock_singleton(tmp_path: Path):
    state = tmp_path / "state"
    lock1 = ProcessLock(state_dir=state, non_blocking=True)
    lock2 = ProcessLock(state_dir=state, non_blocking=True)
    assert lock1.acquire() is True
    assert lock2.acquire() is False
    lock1.release()
    assert lock2.acquire() is True
    lock2.release()


def test_governance_loaded_from_executor_worktree(tmp_path: Path):
    primary = tmp_path / "primary"
    executor = tmp_path / "executor"
    primary.mkdir()
    executor.mkdir()
    (primary / "AGENTS.md").write_text("PRIMARY_GOVERNANCE", encoding="utf-8")
    (executor / "AGENTS.md").write_text("EXECUTOR_GOVERNANCE", encoding="utf-8")
    rules = executor / ".cursor" / "rules"
    rules.mkdir(parents=True)
    (rules / "r.mdc").write_text("RULE_FROM_EXECUTOR", encoding="utf-8")
    text = load_executor_governance(executor)
    assert "EXECUTOR_GOVERNANCE" in text
    assert "RULE_FROM_EXECUTOR" in text
    assert "PRIMARY_GOVERNANCE" not in text


def test_bridge_prompt_outside_worktree_fails(tmp_path: Path):
    bw = tmp_path / "bridge"
    bw.mkdir()
    other = tmp_path / "other" / "next-prompt.md"
    other.parent.mkdir()
    other.write_text(LEGACY_WAIT, encoding="utf-8")
    report = verify_bridge_source(
        bridge_worktree=bw,
        bridge_prompt_path=other,
        expected_repo="kkobanenko/ai-core",
        mode="launch",
        git_runner=_git_ok(),
        require_remote_match=True,
    )
    assert report.ok is False
    assert any("not inside" in r for r in report.reasons)


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
    assert "--print" in calls[0][0]


def test_compose_prompt_preserves_bridge_raw():
    prompt = parse_next_prompt(READY_META)
    composed = compose_executor_prompt(
        governance_text="AGENTS rules here",
        bridge_prompt=prompt,
    )
    assert "AGENTS rules here" in composed
    assert "coord_version: 1" in composed
    assert "executor_worktree" in composed


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


def test_integration_claim_and_fake_executor_exactly_once(tmp_path: Path):
    """EXECUTOR_READY → claim → fake launch once → second invocation no launch."""
    state = tmp_path / "coord-state"
    executor = tmp_path / "executor-wt"
    bridge = tmp_path / "bridge-wt"
    executor.mkdir()
    bridge.mkdir()
    (executor / "AGENTS.md").write_text("gov", encoding="utf-8")

    # Метаданные указывают на этот executor path.
    meta = READY_META.replace("/tmp/example-wt", str(executor))
    prompt_file = bridge / "docs" / "agent-bridge" / "next-prompt.md"
    prompt_file.parent.mkdir(parents=True)
    prompt_file.write_text(meta, encoding="utf-8")

    launches = []

    def fake_runner(args, cwd):
        launches.append(list(args))
        return 0, "fake-ok", ""

    git = _git_ok(
        branch="feat/example",
        head="abc123def456",
        bridge_branch="test/bridge",
        bridge_head="bridgehead001",
        remote_tip="abc123def456",
    )

    first = run_once(
        mode="launch",
        repo_root=tmp_path,
        executor_worktree=executor,
        bridge_prompt_path=prompt_file,
        bridge_worktree=bridge,
        state_dir=state,
        git_runner=git,
        executor_runner=fake_runner,
        agent_bin="fake-agent",
    )
    assert first.executor_launched is True
    assert len(launches) == 1

    second = run_once(
        mode="launch",
        repo_root=tmp_path,
        executor_worktree=executor,
        bridge_prompt_path=prompt_file,
        bridge_worktree=bridge,
        state_dir=state,
        git_runner=git,
        executor_runner=fake_runner,
        agent_bin="fake-agent",
    )
    assert second.executor_launched is False
    assert second.decision.state == CoordState.HUMAN_REQUIRED
    assert len(launches) == 1
    assert "claim" in second.decision.reason.lower() or "already" in second.decision.reason


def test_concurrent_coordinators_at_most_one_launch(tmp_path: Path):
    state = tmp_path / "coord-state"
    executor = tmp_path / "executor-wt"
    bridge = tmp_path / "bridge-wt"
    executor.mkdir()
    bridge.mkdir()
    (executor / "AGENTS.md").write_text("gov", encoding="utf-8")
    meta = READY_META.replace("/tmp/example-wt", str(executor))
    prompt_file = bridge / "docs" / "agent-bridge" / "next-prompt.md"
    prompt_file.parent.mkdir(parents=True)
    prompt_file.write_text(meta, encoding="utf-8")

    launches = []
    lock = threading.Lock()

    def fake_runner(args, cwd):
        with lock:
            launches.append(1)
        return 0, "ok", ""

    git = _git_ok(
        branch="feat/example",
        head="abc123def456",
        bridge_branch="test/bridge",
        bridge_head="bridgehead001",
    )

    results = []

    def worker():
        results.append(
            run_once(
                mode="launch",
                repo_root=tmp_path,
                executor_worktree=executor,
                bridge_prompt_path=prompt_file,
                bridge_worktree=bridge,
                state_dir=state,
                git_runner=git,
                executor_runner=fake_runner,
                agent_bin="fake-agent",
            )
        )

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    launched = sum(1 for r in results if r.executor_launched)
    assert launched == 1
    assert len(launches) == 1


# --- v0.2 publication / postconditions ---

from tools.dev_coordinator.models import FinalStatus
from tools.dev_coordinator.publication import (
    evaluate_postconditions,
    parse_porcelain_paths,
    publish_exact_paths,
)


REPORT = "docs/handoffs/2026-09-12-coordinator-live-pilot-2.md"


def _ready_pub(executor_path: str, **extra: object) -> str:
    fields = {
        "coord_version": 1,
        "state": "EXECUTOR_READY",
        "prompt_id": "pilot2-001",
        "target_repo": "kkobanenko/ai-core",
        "target_branch": "docs/coordinator-live-pilot-readme-audit-20260911",
        "target_worktree": executor_path,
        "base_sha": "abc123def456",
        "hosted_ci": "forbidden",
        "max_executor_runs": 1,
        "allowed_paths": REPORT,
        "required_paths": REPORT,
        "publication_commit": "true",
        "publication_push": "true",
        "commit_message": "docs: complete coordinator live pilot 2",
    }
    fields.update(extra)
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            continue
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append("body")
    return "\n".join(lines)


def test_parse_porcelain_paths():
    text = "?? uv.lock\n?? docs/handoffs/x.md\n M README.md\n"
    paths = parse_porcelain_paths(text)
    assert "uv.lock" in paths
    assert "docs/handoffs/x.md" in paths
    assert "README.md" in paths


def test_publication_requires_paths_when_commit_true():
    text = _meta(
        "EXECUTOR_READY",
        publication_commit=True,
        publication_push=False,
        commit_message="x",
    )
    prompt = parse_next_prompt(text)
    assert prompt.parse_error is not None
    assert "allowed_paths" in prompt.parse_error


def test_pilot1_regression_unexpected_uv_lock(tmp_path: Path):
    """Fake Executor: required report + unexpected uv.lock, exit 0 → no commit/push."""
    state = tmp_path / "coord-state"
    executor = tmp_path / "executor-wt"
    bridge = tmp_path / "bridge-wt"
    executor.mkdir()
    bridge.mkdir()
    (executor / "AGENTS.md").write_text("gov", encoding="utf-8")

    report_rel = "docs/handoffs/2026-09-11-coordinator-live-pilot-readme-audit.md"
    meta = _ready_pub(
        str(executor),
        prompt_id="pilot1-regression",
        allowed_paths=report_rel,
        required_paths=report_rel,
        commit_message="docs: audit README against S1 main state",
    )
    prompt_file = bridge / "docs" / "agent-bridge" / "next-prompt.md"
    prompt_file.parent.mkdir(parents=True)
    prompt_file.write_text(meta, encoding="utf-8")

    def fake_runner(args, cwd):
        # Создаём required + unexpected, как в первом live-pilot.
        report = Path(cwd) / report_rel
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("# audit\n", encoding="utf-8")
        (Path(cwd) / "uv.lock").write_text("# unexpected\n", encoding="utf-8")
        return 0, "fake executor ok", ""

    def git(args, cwd):
        cmd = list(args)
        cwd_s = str(cwd)
        if cmd[:2] == ["branch", "--show-current"]:
            if "bridge" in cwd_s:
                return 0, "test/bridge\n", ""
            return 0, "docs/coordinator-live-pilot-readme-audit-20260911\n", ""
        if cmd[:2] == ["rev-parse", "HEAD"]:
            if "bridge" in cwd_s:
                return 0, "bridgehead001\n", ""
            return 0, "abc123def456\n", ""
        if cmd == ["rev-parse", "--is-inside-work-tree"]:
            return 0, "true\n", ""
        if cmd[:2] == ["status", "--porcelain"]:
            # Pre-launch safety: clean. Post-launch: report + uv.lock.
            if (Path(cwd) / "uv.lock").exists():
                return 0, f"?? {report_rel}\n?? uv.lock\n", ""
            return 0, "", ""
        if cmd[:3] == ["remote", "get-url", "origin"]:
            return 0, "git@github.com:kkobanenko/ai-core.git\n", ""
        if cmd[:2] == ["ls-remote", "origin"]:
            tip = "bridgehead001" if "bridge" in cwd_s else "abc123def456"
            return 0, f"{tip}\t{cmd[2]}\n", ""
        if cmd[:2] == ["diff", "--check"]:
            return 0, "", ""
        if cmd[0] == "add":
            raise AssertionError(f"git add must not run on postcondition fail: {cmd}")
        if cmd[0] == "commit":
            raise AssertionError("git commit must not run")
        if cmd[0] == "push":
            raise AssertionError("git push must not run")
        return 1, "", f"unexpected: {cmd}"

    result = run_once(
        mode="launch",
        repo_root=tmp_path,
        executor_worktree=executor,
        bridge_prompt_path=prompt_file,
        bridge_worktree=bridge,
        state_dir=state,
        git_runner=git,
        executor_runner=fake_runner,
        agent_bin="fake-agent",
    )
    assert result.executor_exit_code == 0
    assert result.postconditions_ok is False
    assert "uv.lock" in result.unexpected_paths
    assert result.commit_created is False
    assert result.push_attempted is False
    assert result.final_status == FinalStatus.POSTCONDITION_FAILED


def test_happy_path_exact_add_commit_push(tmp_path: Path):
    state = tmp_path / "coord-state"
    executor = tmp_path / "executor-wt"
    bridge = tmp_path / "bridge-wt"
    executor.mkdir()
    bridge.mkdir()
    (executor / "AGENTS.md").write_text("gov", encoding="utf-8")

    meta = _ready_pub(str(executor))
    prompt_file = bridge / "docs" / "agent-bridge" / "next-prompt.md"
    prompt_file.parent.mkdir(parents=True)
    prompt_file.write_text(meta, encoding="utf-8")

    git_cmds = []

    def fake_runner(args, cwd):
        report = Path(cwd) / REPORT
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("# pilot2\n", encoding="utf-8")
        return 0, "ok", ""

    def git(args, cwd):
        cmd = list(args)
        git_cmds.append(tuple(cmd))
        cwd_s = str(cwd)
        if cmd[:2] == ["branch", "--show-current"]:
            if "bridge" in cwd_s:
                return 0, "test/bridge\n", ""
            return 0, "docs/coordinator-live-pilot-readme-audit-20260911\n", ""
        if cmd[:2] == ["rev-parse", "HEAD"]:
            if "bridge" in cwd_s:
                return 0, "bridgehead001\n", ""
            # After commit, HEAD becomes newsha.
            if any(c[0] == "commit" for c in git_cmds[:-1]):
                return 0, "newsha001\n", ""
            return 0, "abc123def456\n", ""
        if cmd == ["rev-parse", "--is-inside-work-tree"]:
            return 0, "true\n", ""
        if cmd[:2] == ["status", "--porcelain"]:
            if (Path(cwd) / REPORT).exists():
                return 0, f"?? {REPORT}\n", ""
            return 0, "", ""
        if cmd[:3] == ["remote", "get-url", "origin"]:
            return 0, "git@github.com:kkobanenko/ai-core.git\n", ""
        if cmd[:2] == ["ls-remote", "origin"]:
            if "bridge" in cwd_s:
                return 0, "bridgehead001\trefs/heads/test/bridge\n", ""
            # After push verify.
            if any(c[0] == "push" for c in git_cmds[:-1]):
                return 0, "newsha001\trefs/heads/docs/coordinator-live-pilot-readme-audit-20260911\n", ""
            return 0, "abc123def456\trefs/heads/x\n", ""
        if cmd[:2] == ["diff", "--check"] or cmd[:3] == ["diff", "--cached", "--check"]:
            return 0, "", ""
        if cmd[0] == "add":
            assert cmd[1] == "--"
            assert "." not in cmd
            assert "-A" not in cmd
            assert REPORT in cmd
            return 0, "", ""
        if cmd[0] == "commit":
            return 0, "", ""
        if cmd[0] == "push":
            assert "force" not in " ".join(cmd).lower()
            assert "main" not in cmd[-1]
            return 0, "", ""
        return 1, "", f"unexpected: {cmd}"

    result = run_once(
        mode="launch",
        repo_root=tmp_path,
        executor_worktree=executor,
        bridge_prompt_path=prompt_file,
        bridge_worktree=bridge,
        state_dir=state,
        git_runner=git,
        executor_runner=fake_runner,
        agent_bin="fake-agent",
    )
    assert result.executor_exit_code == 0
    assert result.postconditions_ok is True
    assert result.commit_created is True
    assert result.push_attempted is True
    assert result.publication_verified is True
    assert result.local_head == "newsha001"
    assert result.remote_head == "newsha001"
    assert result.final_status == FinalStatus.WORK_PACKAGE_SUCCESS
    assert not any(c[0] == "add" and "." in c for c in git_cmds)


def test_missing_required_artifact(tmp_path: Path):
    prompt = parse_next_prompt(_ready_pub(str(tmp_path)))
    # Файла нет; porcelain пустой/без report.

    def git(args, cwd):
        cmd = list(args)
        if cmd[:2] == ["status", "--porcelain"]:
            return 0, "", ""
        if cmd[:2] == ["diff", "--check"]:
            return 0, "", ""
        return 1, "", "unexpected"

    post = evaluate_postconditions(prompt, executor_worktree=tmp_path, git_runner=git)
    assert post.ok is False
    assert post.required_paths_ok is False
    assert post.final_status == FinalStatus.POSTCONDITION_FAILED


def test_unexpected_tracked_file(tmp_path: Path):
    prompt = parse_next_prompt(_ready_pub(str(tmp_path)))
    report = tmp_path / REPORT
    report.parent.mkdir(parents=True)
    report.write_text("ok", encoding="utf-8")

    def git(args, cwd):
        cmd = list(args)
        if cmd[:2] == ["status", "--porcelain"]:
            return 0, f"A  {REPORT}\n M README.md\n", ""
        if cmd[:2] == ["diff", "--check"]:
            return 0, "", ""
        return 1, "", "unexpected"

    post = evaluate_postconditions(prompt, executor_worktree=tmp_path, git_runner=git)
    assert post.ok is False
    assert "README.md" in post.unexpected_paths


def test_diff_check_failure(tmp_path: Path):
    prompt = parse_next_prompt(_ready_pub(str(tmp_path)))
    report = tmp_path / REPORT
    report.parent.mkdir(parents=True)
    report.write_text("ok", encoding="utf-8")

    def git(args, cwd):
        cmd = list(args)
        if cmd[:2] == ["status", "--porcelain"]:
            return 0, f"?? {REPORT}\n", ""
        if cmd[:2] == ["diff", "--check"]:
            return 2, "whitespace error\n", ""
        return 1, "", "unexpected"

    post = evaluate_postconditions(prompt, executor_worktree=tmp_path, git_runner=git)
    assert post.ok is False
    assert post.final_status == FinalStatus.VALIDATION_FAILED


def test_refuse_publish_to_main(tmp_path: Path):
    text = _ready_pub(str(tmp_path), target_branch="main")
    prompt = parse_next_prompt(text)
    pub = publish_exact_paths(
        prompt,
        executor_worktree=tmp_path,
        paths_to_stage=[REPORT],
        git_runner=lambda a, c: (0, "", ""),
    )
    assert pub.commit_created is False
    assert "main" in pub.reason


def test_commit_failure(tmp_path: Path):
    prompt = parse_next_prompt(_ready_pub(str(tmp_path)))

    def git(args, cwd):
        cmd = list(args)
        if cmd[0] == "add":
            return 0, "", ""
        if cmd[:3] == ["diff", "--cached", "--check"]:
            return 0, "", ""
        if cmd[0] == "commit":
            return 1, "", "commit failed"
        return 1, "", f"unexpected {cmd}"

    pub = publish_exact_paths(
        prompt,
        executor_worktree=tmp_path,
        paths_to_stage=[REPORT],
        git_runner=git,
    )
    assert pub.commit_created is False
    assert pub.final_status == FinalStatus.PUBLICATION_FAILED


def test_push_failure(tmp_path: Path):
    prompt = parse_next_prompt(_ready_pub(str(tmp_path)))

    def git(args, cwd):
        cmd = list(args)
        if cmd[0] == "add":
            return 0, "", ""
        if cmd[:3] == ["diff", "--cached", "--check"]:
            return 0, "", ""
        if cmd[0] == "commit":
            return 0, "", ""
        if cmd[:2] == ["rev-parse", "HEAD"]:
            return 0, "localsha\n", ""
        if cmd[0] == "push":
            return 1, "", "push denied"
        return 1, "", f"unexpected {cmd}"

    pub = publish_exact_paths(
        prompt,
        executor_worktree=tmp_path,
        paths_to_stage=[REPORT],
        git_runner=git,
    )
    assert pub.commit_created is True
    assert pub.push_attempted is True
    assert pub.publication_verified is False
    assert pub.final_status == FinalStatus.PUBLICATION_FAILED


def test_remote_sha_mismatch(tmp_path: Path):
    prompt = parse_next_prompt(_ready_pub(str(tmp_path)))

    def git(args, cwd):
        cmd = list(args)
        if cmd[0] == "add":
            return 0, "", ""
        if cmd[:3] == ["diff", "--cached", "--check"]:
            return 0, "", ""
        if cmd[0] == "commit":
            return 0, "", ""
        if cmd[:2] == ["rev-parse", "HEAD"]:
            return 0, "localsha\n", ""
        if cmd[0] == "push":
            return 0, "", ""
        if cmd[:2] == ["ls-remote", "origin"]:
            return 0, "othersha\trefs/heads/x\n", ""
        return 1, "", f"unexpected {cmd}"

    pub = publish_exact_paths(
        prompt,
        executor_worktree=tmp_path,
        paths_to_stage=[REPORT],
        git_runner=git,
    )
    assert pub.publication_verified is False
    assert pub.final_status == FinalStatus.PUBLICATION_UNVERIFIED


def test_executor_nonzero_no_publication(tmp_path: Path):
    state = tmp_path / "coord-state"
    executor = tmp_path / "executor-wt"
    bridge = tmp_path / "bridge-wt"
    executor.mkdir()
    bridge.mkdir()
    (executor / "AGENTS.md").write_text("gov", encoding="utf-8")
    meta = _ready_pub(str(executor))
    prompt_file = bridge / "docs" / "agent-bridge" / "next-prompt.md"
    prompt_file.parent.mkdir(parents=True)
    prompt_file.write_text(meta, encoding="utf-8")

    def fake_runner(args, cwd):
        return 7, "", "boom"

    def git(args, cwd):
        cmd = list(args)
        cwd_s = str(cwd)
        if cmd[:2] == ["branch", "--show-current"]:
            if "bridge" in cwd_s:
                return 0, "test/bridge\n", ""
            return 0, "docs/coordinator-live-pilot-readme-audit-20260911\n", ""
        if cmd[:2] == ["rev-parse", "HEAD"]:
            if "bridge" in cwd_s:
                return 0, "bridgehead001\n", ""
            return 0, "abc123def456\n", ""
        if cmd == ["rev-parse", "--is-inside-work-tree"]:
            return 0, "true\n", ""
        if cmd[:2] == ["status", "--porcelain"]:
            return 0, "", ""
        if cmd[:3] == ["remote", "get-url", "origin"]:
            return 0, "git@github.com:kkobanenko/ai-core.git\n", ""
        if cmd[:2] == ["ls-remote", "origin"]:
            tip = "bridgehead001" if "bridge" in cwd_s else "abc123def456"
            return 0, f"{tip}\trefs/heads/x\n", ""
        if cmd[0] in ("add", "commit", "push"):
            raise AssertionError("publication must not run after nonzero exit")
        return 1, "", f"unexpected {cmd}"

    result = run_once(
        mode="launch",
        repo_root=tmp_path,
        executor_worktree=executor,
        bridge_prompt_path=prompt_file,
        bridge_worktree=bridge,
        state_dir=state,
        git_runner=git,
        executor_runner=fake_runner,
        agent_bin="fake-agent",
    )
    assert result.executor_exit_code == 7
    assert result.commit_created is False
    assert result.push_attempted is False
    assert result.final_status == FinalStatus.EXECUTOR_NONZERO


def test_compose_prompt_forbids_executor_commit():
    prompt = parse_next_prompt(READY_META)
    composed = compose_executor_prompt(
        governance_text="gov",
        bridge_prompt=prompt,
    )
    assert "MUST NOT" in composed
    assert "git commit" in composed
    assert "Coordinator owns these" in composed
