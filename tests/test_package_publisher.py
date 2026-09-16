"""Тесты Architect work-package publisher (без live GitHub / systemd)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.dev_coordinator.managed_worktrees import derive_executor_worktree_path
from tools.dev_coordinator.parse import parse_next_prompt
from tools.dev_coordinator.package_publisher import (
    WorkPackageSpec,
    _assert_git_command_allowed,
    _FORBIDDEN_GIT_PREFIXES,
    publish_work_package,
    read_checkout_snapshot,
    render_next_prompt,
    resolve_bridge_branch,
    snapshots_equal,
)
from tools.dev_coordinator.runner_config import parse_runner_config

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PUBLISH_SCRIPT = _REPO_ROOT / "scripts" / "publish_dev_coordinator_package.py"

_BASE_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_BRIDGE_SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
_OTHER_SHA = "cccccccccccccccccccccccccccccccccccccccc"


def _make_runner_config(tmp_path: Path, clone: Path) -> Path:
    """Записать минимальный runner.json для тестов."""
    coord = tmp_path / "coord"
    managed = tmp_path / "worktrees"
    agent = tmp_path / "agent"
    for d in (coord, managed, clone):
        d.mkdir(parents=True, exist_ok=True)
    agent.write_text("#!/bin/sh\n", encoding="utf-8")
    agent.chmod(0o755)
    cfg_path = tmp_path / "runner.json"
    cfg_path.write_text(
        json.dumps(
            {
                "poll_interval_seconds": 15,
                "coordinator_repo_root": str(coord),
                "managed_worktree_root": str(managed),
                "agent_bin": str(agent),
                "bridge_prefix": "coord/bridge/",
                "repositories": {
                    "kkobanenko/ai-core": str(clone),
                },
            }
        ),
        encoding="utf-8",
    )
    return cfg_path


def _base_spec(
    tmp_path: Path,
    clone: Path,
    *,
    dry_run: bool = False,
    target_branch: str = "feat/test-pkg",
    bridge_branch: str = "coord/bridge/test-pkg",
    base_sha: str = _BASE_SHA,
) -> WorkPackageSpec:
    cfg = _make_runner_config(tmp_path, clone)
    config = parse_runner_config(json.loads(cfg.read_text()))
    wt = derive_executor_worktree_path(
        config.managed_worktree_root, "kkobanenko/ai-core", target_branch
    )
    return WorkPackageSpec(
        runner_config_path=cfg,
        bridge_repo="kkobanenko/ai-core",
        target_repo="kkobanenko/ai-core",
        base_sha=base_sha,
        target_branch=target_branch,
        bridge_branch=bridge_branch,
        prompt_id="test-pkg-001",
        allowed_paths=("foo.py",),
        required_paths=("foo.py",),
        transient_paths=(),
        commit_message="feat: test package",
        hosted_ci="forbidden",
        publication_commit=True,
        publication_push=True,
        max_executor_runs=1,
        instruction_body="# Task\n\nDo work.\n",
        dry_run=dry_run,
    )


class FakeRemoteState:
    """In-memory симуляция remote refs для injected git runner."""

    def __init__(self) -> None:
        self.refs: dict[str, str] = {}
        self.objects: dict[str, str] = {}
        self.commands: list[tuple[list[str], str]] = []
        self.head = _BASE_SHA
        self.origin = "git@github.com:kkobanenko/ai-core.git"
        self.dirty_status = ""

    def runner(self, args, cwd):
        cmd = list(args)
        self.commands.append((cmd, str(cwd)))
        if cmd[:3] == ["remote", "get-url", "origin"]:
            return 0, self.origin + "\n", ""
        if cmd[:2] == ["ls-remote", "origin"] and len(cmd) >= 3:
            ref = cmd[2]
            branch = ref.replace("refs/heads/", "")
            sha = self.refs.get(branch)
            if sha:
                return 0, f"{sha}\t{ref}\n", ""
            return 0, "", ""
        if cmd[:2] == ["cat-file", "-e"]:
            spec = cmd[2]
            sha = spec.replace("^{commit}", "")
            if sha in (self.head, _BASE_SHA, _BRIDGE_SHA, _OTHER_SHA):
                return 0, "", ""
            return 1, "", "not found"
        if cmd[:2] == ["rev-parse", "HEAD"]:
            return 0, self.head + "\n", ""
        if cmd[:2] == ["rev-parse", "--is-inside-work-tree"]:
            return 0, "true\n", ""
        if cmd[:2] == ["branch", "--show-current"]:
            return 0, "main\n", ""
        if cmd[:2] == ["status", "--porcelain"]:
            return 0, self.dirty_status, ""
        if cmd[:2] == ["diff", "--cached", "--stat"]:
            return 0, "", ""
        if cmd[:2] == ["show"]:
            # show <sha>:path
            spec = cmd[1]
            sha, path = spec.split(":", 1)
            key = f"{sha}:{path}"
            if key in self.objects:
                return 0, self.objects[key], ""
            return 1, "", "missing"
        if cmd[:2] == ["push", "origin"]:
            refspec = cmd[2]
            if ":" not in refspec:
                return 1, "", "invalid refspec"
            src, dst = refspec.split(":", 1)
            branch = dst.replace("refs/heads/", "")
            self.refs[branch] = src
            return 0, "", ""
        # commit-tree plumbing: делегируем минимально для тестов publish
        if cmd[0] == "read-tree":
            return 0, "", ""
        if cmd[0] == "update-index":
            return 0, "", ""
        if cmd[0] == "write-tree":
            return 0, "tree0001\n", ""
        if cmd[0] == "commit-tree":
            new_sha = _BRIDGE_SHA if _BRIDGE_SHA not in self.refs.values() else _OTHER_SHA
            return 0, new_sha + "\n", ""
        return 1, "", f"unexpected: {cmd}"


def test_prompt_rendering_parses_with_parse_next_prompt(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    config = parse_runner_config(json.loads(spec.runner_config_path.read_text()))
    wt = derive_executor_worktree_path(
        config.managed_worktree_root, spec.target_repo, spec.target_branch
    )
    text = render_next_prompt(spec=spec, target_worktree=wt)
    parsed = parse_next_prompt(text)
    assert parsed.parse_error is None
    assert parsed.state is not None
    assert parsed.state.value == "EXECUTOR_READY"
    assert parsed.prompt_id == spec.prompt_id
    assert parsed.target_worktree == str(wt)


def test_deterministic_target_worktree_derivation(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone, target_branch="feat/my-feature")
    config = parse_runner_config(json.loads(spec.runner_config_path.read_text()))
    expected = derive_executor_worktree_path(
        config.managed_worktree_root, "kkobanenko/ai-core", "feat/my-feature"
    )
    text = render_next_prompt(spec=spec, target_worktree=expected)
    parsed = parse_next_prompt(text)
    assert parsed.target_worktree == str(expected)


def test_resolve_bridge_branch_from_package_id() -> None:
    assert resolve_bridge_branch(bridge_branch=None, package_id="pkg-001") == (
        "coord/bridge/pkg-001"
    )


def test_bridge_outside_namespace_fail_closed(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone, bridge_branch="feat/not-bridge")
    remote = FakeRemoteState()
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert not outcome.ok
    assert any("outside namespace" in e for e in outcome.errors)


def test_target_wrong_sha_fail_closed(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    remote = FakeRemoteState()
    remote.refs[spec.target_branch] = _OTHER_SHA
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert not outcome.ok
    assert any("target remote SHA mismatch" in e for e in outcome.errors)


def test_target_branch_absent_creates_at_base(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    remote = FakeRemoteState()
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert outcome.ok
    assert remote.refs[spec.target_branch] == _BASE_SHA
    assert outcome.bridge_remote_sha is not None


def test_target_exact_base_resumable(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    remote = FakeRemoteState()
    remote.refs[spec.target_branch] = _BASE_SHA
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert outcome.ok
    assert outcome.resumed_target


def test_existing_bridge_differing_package_fail_closed(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    remote = FakeRemoteState()
    remote.refs[spec.target_branch] = _BASE_SHA
    remote.refs[spec.bridge_branch] = _BRIDGE_SHA
    remote.objects[f"{_BRIDGE_SHA}:docs/agent-bridge/next-prompt.md"] = (
        "---\nstate: WAIT\n---\n"
    )
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert not outcome.ok
    assert any("differs" in e for e in outcome.errors)


def test_identical_package_rerun_idempotent(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    remote = FakeRemoteState()
    remote.refs[spec.target_branch] = _BASE_SHA
    config = parse_runner_config(json.loads(spec.runner_config_path.read_text()))
    wt = derive_executor_worktree_path(
        config.managed_worktree_root, spec.target_repo, spec.target_branch
    )
    prompt = render_next_prompt(spec=spec, target_worktree=wt)
    remote.refs[spec.bridge_branch] = _BRIDGE_SHA
    remote.objects[f"{_BRIDGE_SHA}:docs/agent-bridge/next-prompt.md"] = prompt

    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert outcome.ok
    assert outcome.resumed_bridge
    push_cmds = [c for c, _ in remote.commands if c[:2] == ["push", "origin"]]
    assert push_cmds == []


def _init_clone_with_origin(tmp_path: Path) -> tuple[Path, str]:
    """Bare remote + clone с origin kkobanenko/ai-core."""
    bare = tmp_path / "remote.git"
    clone = tmp_path / "clone"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    subprocess.run(
        ["git", "clone", str(bare), str(clone)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "set-url", "origin", "git@github.com:kkobanenko/ai-core.git"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    (clone / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=clone, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=clone,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "push", "-u", "origin", "main"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    return clone, head


def test_dry_run_no_push_commands(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone, dry_run=True)
    remote = FakeRemoteState()
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert outcome.ok
    assert outcome.dry_run
    assert not any(c[0] == "push" for c, _ in remote.commands)


def test_forbidden_git_commands_rejected() -> None:
    with pytest.raises(ValueError, match="forbidden"):
        _assert_git_command_allowed(("reset", "--hard", "HEAD"))
    with pytest.raises(ValueError, match="forbidden"):
        _assert_git_command_allowed(("push", "origin", "+refs/heads/x"))


def test_dirty_primary_checkout_preserved(tmp_path: Path) -> None:
    """Реальный git: dirty clone остаётся неизменным после dry-run."""
    clone, head = _init_clone_with_origin(tmp_path)
    dirty_file = clone / "dirty.txt"
    dirty_file.write_text("changed\n", encoding="utf-8")

    spec = _base_spec(tmp_path, clone, dry_run=True, base_sha=head)
    before = read_checkout_snapshot(clone, _real_git_session())
    outcome = publish_work_package(spec)
    after = read_checkout_snapshot(clone, _real_git_session())
    assert outcome.ok
    assert snapshots_equal(before, after)
    assert "changed" in dirty_file.read_text()


def test_dry_run_mutation_boundary(tmp_path: Path) -> None:
    """Dry-run не меняет refs remote (ls-remote до/после через fake)."""
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone, dry_run=True)
    remote = FakeRemoteState()
    refs_before = dict(remote.refs)
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert outcome.ok
    assert remote.refs == refs_before


def test_cli_unrelated_cwd_bootstrap(tmp_path: Path) -> None:
    """Запуск из чужого cwd не подхватывает локальный tools/."""
    shadow = tmp_path / "shadow_project"
    shadow.mkdir()
    (shadow / "tools").mkdir()
    (shadow / "tools" / "dev_coordinator").mkdir(parents=True)
    (shadow / "tools" / "dev_coordinator" / "__init__.py").write_text(
        "raise ImportError('shadow')\n",
        encoding="utf-8",
    )
    instr = tmp_path / "task.md"
    instr.write_text("# Task\n", encoding="utf-8")
    clone, head = _init_clone_with_origin(tmp_path)
    cfg = _make_runner_config(tmp_path, clone)

    proc = subprocess.run(
        [
            sys.executable,
            str(_PUBLISH_SCRIPT),
            "--runner-config",
            str(cfg),
            "--bridge-repo",
            "kkobanenko/ai-core",
            "--target-repo",
            "kkobanenko/ai-core",
            "--base-sha",
            head,
            "--target-branch",
            "feat/cli-test",
            "--package-id",
            "cli-test",
            "--prompt-id",
            "cli-001",
            "--allowed-paths",
            "a.py",
            "--required-paths",
            "a.py",
            "--commit-message",
            "test",
            "--instruction-file",
            str(instr),
            "--dry-run",
        ],
        cwd=str(shadow),
        capture_output=True,
        text=True,
    )
    assert "shadow" not in (proc.stderr or "")
    assert proc.returncode in (0, 1)


def _real_git_session():
    from tools.dev_coordinator.package_publisher import _GitSession
    from tools.dev_coordinator.gitutil import default_git_runner

    return _GitSession(git_runner=default_git_runner)


def test_publish_never_issues_forbidden_git_commands(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    remote = FakeRemoteState()
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert outcome.ok
    forbidden_starts = {f[0] for f in _FORBIDDEN_GIT_PREFIXES}
    for cmd in outcome.git_commands:
        assert cmd[0] not in forbidden_starts
        if cmd[0] == "push":
            assert "--force" not in cmd
            assert "-f" not in cmd


def test_target_main_rejected(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone, target_branch="main")
    remote = FakeRemoteState()
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert not outcome.ok
    assert any("forbidden target branch" in e for e in outcome.errors)
