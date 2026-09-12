"""Тесты persistent Coordinator runner (без live systemd/Cursor/GitHub)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import pytest

from tools.dev_coordinator.managed_worktrees import (
    derive_bridge_worktree_path,
    derive_executor_worktree_path,
    is_path_contained,
    prepare_bridge_worktree,
    prepare_executor_worktree,
    validate_declared_executor_path,
)
from tools.dev_coordinator.models import FinalStatus
from tools.dev_coordinator.runner import (
    BridgeCandidate,
    discover_bridge_refs,
    is_terminal_package,
    load_runner_state,
    map_final_status,
    package_key,
    process_candidate,
    record_package_result,
    save_runner_state,
    scan_repositories,
    validate_candidate,
)
from tools.dev_coordinator.runner_config import load_runner_config, parse_runner_config

READY_PROMPT = """---
coord_version: 1
state: EXECUTOR_READY
prompt_id: pkg-001
target_repo: kkobanenko/ai-core
target_branch: feat/example
target_worktree: {target_wt}
base_sha: abc123def4567890abcdef1234567890abcdef12
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: foo.py
required_paths: foo.py
publication_commit: true
publication_push: true
commit_message: test
---

# Task
body
"""


def _make_config(tmp_path: Path) -> RunnerConfig:
    coord = tmp_path / "coord"
    managed = tmp_path / "worktrees"
    ai_core = tmp_path / "ai-core-clone"
    agent = tmp_path / "agent"
    for d in (coord, managed, ai_core):
        d.mkdir()
    agent.write_text("#!/bin/sh\n", encoding="utf-8")
    agent.chmod(0o755)
    return parse_runner_config(
        {
            "poll_interval_seconds": 15,
            "coordinator_repo_root": str(coord),
            "managed_worktree_root": str(managed),
            "agent_bin": str(agent),
            "bridge_prefix": "coord/bridge/",
            "repositories": {
                "kkobanenko/ai-core": str(ai_core),
            },
        }
    )


def _executor_wt(config: RunnerConfig, branch: str = "feat/example") -> Path:
    return derive_executor_worktree_path(
        config.managed_worktree_root, "kkobanenko/ai-core", branch
    )


def _ready_prompt(config: RunnerConfig, branch: str = "feat/example") -> str:
    wt = _executor_wt(config, branch)
    return READY_PROMPT.format(target_wt=wt)


class TestRunnerConfig:
    def test_valid_config(self, tmp_path: Path) -> None:
        cfg = _make_config(tmp_path)
        assert cfg.poll_interval_seconds == 15
        assert cfg.bridge_prefix == "coord/bridge/"

    def test_reject_unknown_key(self, tmp_path: Path) -> None:
        coord = tmp_path / "coord"
        managed = tmp_path / "wt"
        clone = tmp_path / "clone"
        agent = tmp_path / "agent"
        for d in (coord, managed, clone):
            d.mkdir()
        agent.write_text("x", encoding="utf-8")
        data = {
            "poll_interval_seconds": 15,
            "coordinator_repo_root": str(coord),
            "managed_worktree_root": str(managed),
            "agent_bin": str(agent),
            "bridge_prefix": "coord/bridge/",
            "repositories": {"kkobanenko/ai-core": str(clone)},
            "extra": True,
        }
        with pytest.raises(ValueError, match="unknown config keys"):
            parse_runner_config(data)

    def test_reject_relative_path(self, tmp_path: Path) -> None:
        coord = tmp_path / "coord"
        managed = tmp_path / "wt"
        clone = tmp_path / "clone"
        agent = tmp_path / "agent"
        for d in (coord, managed, clone):
            d.mkdir()
        agent.write_text("x", encoding="utf-8")
        data = {
            "poll_interval_seconds": 15,
            "coordinator_repo_root": "relative/path",
            "managed_worktree_root": str(managed),
            "agent_bin": str(agent),
            "bridge_prefix": "coord/bridge/",
            "repositories": {"kkobanenko/ai-core": str(clone)},
        }
        with pytest.raises(ValueError, match="absolute path"):
            parse_runner_config(data)

    def test_reject_bad_poll_interval(self, tmp_path: Path) -> None:
        cfg = _make_config(tmp_path)
        raw = {
            "poll_interval_seconds": 2,
            "coordinator_repo_root": str(cfg.coordinator_repo_root),
            "managed_worktree_root": str(cfg.managed_worktree_root),
            "agent_bin": str(cfg.agent_bin),
            "bridge_prefix": "coord/bridge/",
            "repositories": {
                "kkobanenko/ai-core": str(cfg.repositories["kkobanenko/ai-core"]),
            },
        }
        with pytest.raises(ValueError, match="poll_interval_seconds"):
            parse_runner_config(raw)

    def test_reject_duplicate_clone_paths(self, tmp_path: Path) -> None:
        coord = tmp_path / "coord"
        managed = tmp_path / "wt"
        clone = tmp_path / "clone"
        agent = tmp_path / "agent"
        for d in (coord, managed, clone):
            d.mkdir()
        agent.write_text("x", encoding="utf-8")
        data = {
            "poll_interval_seconds": 15,
            "coordinator_repo_root": str(coord),
            "managed_worktree_root": str(managed),
            "agent_bin": str(agent),
            "bridge_prefix": "coord/bridge/",
            "repositories": {
                "kkobanenko/ai-core": str(clone),
                "kkobanenko/other": str(clone),
            },
        }
        with pytest.raises(ValueError, match="duplicate"):
            parse_runner_config(data)

    def test_load_from_file(self, tmp_path: Path) -> None:
        cfg = _make_config(tmp_path)
        path = tmp_path / "runner.json"
        path.write_text(
            json.dumps(
                {
                    "poll_interval_seconds": 15,
                    "coordinator_repo_root": str(cfg.coordinator_repo_root),
                    "managed_worktree_root": str(cfg.managed_worktree_root),
                    "agent_bin": str(cfg.agent_bin),
                    "bridge_prefix": "coord/bridge/",
                    "repositories": {
                        "kkobanenko/ai-core": str(
                            cfg.repositories["kkobanenko/ai-core"]
                        ),
                    },
                }
            ),
            encoding="utf-8",
        )
        loaded = load_runner_config(path)
        assert loaded.poll_interval_seconds == 15


class TestManagedWorktrees:
    def test_path_containment(self, tmp_path: Path) -> None:
        root = tmp_path / "managed"
        root.mkdir()
        child = root / "ai-core" / "feat"
        assert is_path_contained(child, root)
        outside = tmp_path / "outside"
        outside.mkdir()
        assert not is_path_contained(outside, root)

    def test_forbidden_target_branch(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        clone = config.repositories["kkobanenko/ai-core"]

        def git_runner(args, cwd):
            return 0, "", ""

        result = prepare_executor_worktree(
            repo_clone=clone,
            canonical_repo="kkobanenko/ai-core",
            target_branch="main",
            base_sha="abc",
            declared_worktree=derive_executor_worktree_path(
                config.managed_worktree_root, "kkobanenko/ai-core", "main"
            ),
            managed_root=config.managed_worktree_root,
            git_runner=git_runner,
        )
        assert not result.ok
        assert "forbidden" in result.reason

    def test_declared_path_outside_root(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        outside = tmp_path / "outside" / "wt"
        ok, reason, _ = validate_declared_executor_path(
            outside,
            config.managed_worktree_root,
            "kkobanenko/ai-core",
            "feat/example",
        )
        assert not ok
        assert "outside managed root" in reason

    def test_prepare_and_reuse_bridge_worktree(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        clone = config.repositories["kkobanenko/ai-core"]
        branch = "coord/bridge/pkg-001"
        sha = "bridge_sha_001"
        wt_path = derive_bridge_worktree_path(
            config.managed_worktree_root, "kkobanenko/ai-core", branch
        )

        worktrees: dict[str, dict[str, str]] = {}

        def git_runner(args, cwd):
            cmd = list(args)
            if cmd[:2] == ["worktree", "list"]:
                lines = []
                for p, info in worktrees.items():
                    lines.append(f"worktree {p}")
                    lines.append(f"branch {info['branch']}")
                return 0, "\n".join(lines) + "\n", ""
            if cmd[:2] == ["ls-remote", "origin"]:
                return 0, f"{sha}\trefs/heads/{branch}\n", ""
            if cmd[:3] == ["show-ref", "--verify"]:
                return 1, "", ""
            if cmd[:2] == ["worktree", "add"]:
                wt_path.mkdir(parents=True, exist_ok=True)
                worktrees[str(wt_path)] = {"branch": branch, "sha": sha}
                return 0, "", ""
            if cmd[:2] == ["branch", "--show-current"]:
                return 0, branch + "\n", ""
            if cmd[:2] == ["rev-parse", "HEAD"]:
                return 0, sha + "\n", ""
            if cmd == ["rev-parse", "--is-inside-work-tree"]:
                return 0, "true\n", ""
            if cmd[:2] == ["status", "--porcelain"]:
                return 0, "", ""
            if cmd[:2] == ["remote", "get-url", "origin"]:
                return 0, "git@github.com:kkobanenko/ai-core.git\n", ""
            return 0, "", ""

        first = prepare_bridge_worktree(
            repo_clone=clone,
            canonical_repo="kkobanenko/ai-core",
            bridge_branch=branch,
            bridge_sha=sha,
            managed_root=config.managed_worktree_root,
            git_runner=git_runner,
        )
        assert first.ok
        assert first.created

        second = prepare_bridge_worktree(
            repo_clone=clone,
            canonical_repo="kkobanenko/ai-core",
            bridge_branch=branch,
            bridge_sha=sha,
            managed_root=config.managed_worktree_root,
            git_runner=git_runner,
        )
        assert second.ok
        assert not second.created


class TestRunnerDiscovery:
    def test_discover_only_coord_bridge_refs(self, tmp_path: Path) -> None:
        clone = tmp_path / "clone"
        clone.mkdir()

        def git_runner(args, cwd):
            if args[:2] == ("for-each-ref",):
                out = (
                    "aaa111 refs/remotes/origin/coord/bridge/pkg-a\n"
                    "bbb222 refs/remotes/origin/test/old-bridge\n"
                )
                # Эмулируем только coord/bridge через фильтр runner.
                lines = []
                for line in out.splitlines():
                    ref = line.split()[1]
                    if "/coord/bridge/" in ref:
                        branch = ref.replace("refs/remotes/origin/", "")
                        lines.append(f"{line.split()[0]} {branch}")
                return 0, "\n".join(lines) + "\n", ""
            return 0, "", ""

        refs, err = discover_bridge_refs(clone, "coord/bridge/", git_runner)
        assert err is None
        assert refs == [("coord/bridge/pkg-a", "aaa111")]

    def test_ignore_test_prefix_branches_in_scan(self, tmp_path: Path) -> None:
        """Старые test/* bridge не попадают в discovery namespace."""
        config = _make_config(tmp_path)
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        state_path = state_dir / "runner-state.json"

        prompts = {
            "coord/bridge/new-pkg": _ready_prompt(config),
        }

        launch_count = 0

        def fake_coordinator(**kwargs):
            nonlocal launch_count
            launch_count += 1
            from tools.dev_coordinator.models import Action, Decision, RunResult

            return RunResult(
                mode="launch",
                decision=Decision(
                    action=Action.LAUNCH_EXECUTOR,
                    state=None,
                    reason="ok",
                    would_launch=True,
                ),
                executor_launched=True,
                executor_exit_code=0,
                messages=(),
                final_status=FinalStatus.WORK_PACKAGE_SUCCESS,
            )

        def git_runner(args, cwd):
            cmd = list(args)
            if cmd[:2] == ["fetch", "origin"]:
                return 0, "", ""
            if cmd[:2] == ["for-each-ref"]:
                # Только coord/bridge в выводе for-each-ref (test/* отфильтрован git).
                return (
                    0,
                    "sha1 coord/bridge/new-pkg\n",
                    "",
                )
            if cmd[:2] == ["show"]:
                ref = cmd[1].split(":")[0]
                branch = "coord/bridge/new-pkg"
                if ref == "sha1":
                    return 0, prompts[branch], ""
                return 1, "", "missing"
            if cmd[:2] == ["ls-remote", "origin"]:
                branch = cmd[2].replace("refs/heads/", "")
                if branch == "feat/example":
                    return 0, "abc123def4567890abcdef1234567890abcdef12\n", ""
                if branch.startswith("coord/bridge/"):
                    return 0, "sha1\n", ""
                return 0, "", ""
            if cmd[:2] == ["worktree", "list"]:
                return 0, "", ""
            if cmd[:3] == ["show-ref", "--verify"]:
                return 1, "", ""
            if cmd[:2] == ["worktree", "add"]:
                path = Path(cmd[3])
                path.mkdir(parents=True, exist_ok=True)
                return 0, "", ""
            if cmd[:2] == ["branch", "--show-current"]:
                branch = "feat/example"
                if "bridge" in str(cwd):
                    branch = "coord/bridge/new-pkg"
                return 0, branch + "\n", ""
            if cmd[:2] == ["rev-parse", "HEAD"]:
                if "bridge" in str(cwd):
                    return 0, "sha1\n", ""
                return 0, "abc123def4567890abcdef1234567890abcdef12\n", ""
            if cmd == ["rev-parse", "--is-inside-work-tree"]:
                return 0, "true\n", ""
            if cmd[:2] == ["status", "--porcelain"]:
                return 0, "", ""
            if cmd[:2] == ["remote", "get-url", "origin"]:
                return 0, "git@github.com:kkobanenko/ai-core.git\n", ""
            return 0, "", ""

        summary = scan_repositories(
            config,
            git_runner=git_runner,
            coordinator_invoker=fake_coordinator,
            state_dir=state_dir,
            state_path=state_path,
        )
        assert summary["candidates_found"] == 1
        assert launch_count == 1

        # Повторный scan с тем же SHA — без повторного launch.
        summary2 = scan_repositories(
            config,
            git_runner=git_runner,
            coordinator_invoker=fake_coordinator,
            state_dir=state_dir,
            state_path=state_path,
        )
        assert summary2["skipped_terminal"] == 1
        assert launch_count == 1


class TestRunnerState:
    def test_terminal_idempotency(self, tmp_path: Path) -> None:
        state_path = tmp_path / "runner-state.json"
        state = load_runner_state(state_path)
        key = package_key(
            "kkobanenko/ai-core", "coord/bridge/pkg", "sha_old"
        )
        record_package_result(
            state,
            key=key,
            bridge_repo="kkobanenko/ai-core",
            bridge_branch="coord/bridge/pkg",
            bridge_sha="sha_old",
            prompt_id="p1",
            target_repo="kkobanenko/ai-core",
            target_branch="feat/x",
            status="SUCCESS",
            reason="ok",
        )
        save_runner_state(state_path, state)
        reloaded = load_runner_state(state_path)
        assert is_terminal_package(reloaded, key)

    def test_changed_sha_not_terminal(self, tmp_path: Path) -> None:
        state_path = tmp_path / "runner-state.json"
        state = load_runner_state(state_path)
        key_old = package_key(
            "kkobanenko/ai-core", "coord/bridge/pkg", "sha_old"
        )
        record_package_result(
            state,
            key=key_old,
            bridge_repo="kkobanenko/ai-core",
            bridge_branch="coord/bridge/pkg",
            bridge_sha="sha_old",
            prompt_id="p1",
            target_repo="kkobanenko/ai-core",
            target_branch="feat/x",
            status="SUCCESS",
            reason="ok",
        )
        key_new = package_key(
            "kkobanenko/ai-core", "coord/bridge/pkg", "sha_new"
        )
        assert is_terminal_package(state, key_old)
        assert not is_terminal_package(state, key_new)


class TestRunnerSerialAndErrors:
    def test_serial_execution(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        active = {"count": 0, "max": 0}

        def fake_coordinator(**kwargs):
            active["count"] += 1
            active["max"] = max(active["max"], active["count"])
            from tools.dev_coordinator.models import Action, Decision, RunResult

            result = RunResult(
                mode="launch",
                decision=Decision(
                    action=Action.NONE,
                    state=None,
                    reason="done",
                    would_launch=False,
                ),
                executor_launched=False,
                executor_exit_code=None,
                messages=(),
                final_status=FinalStatus.HUMAN_REQUIRED,
            )
            active["count"] -= 1
            return result

        wt_other = derive_executor_worktree_path(
            config.managed_worktree_root, "kkobanenko/ai-core", "feat/other"
        )
        prompt_other = READY_PROMPT.format(target_wt=wt_other).replace(
            "target_branch: feat/example", "target_branch: feat/other"
        )
        candidates = [
            BridgeCandidate(
                "kkobanenko/ai-core",
                "coord/bridge/a",
                "s1",
                _ready_prompt(config),
            ),
            BridgeCandidate(
                "kkobanenko/ai-core",
                "coord/bridge/b",
                "s2",
                prompt_other,
            ),
        ]

        def git_runner(args, cwd):
            cmd = list(args)
            if cmd[:2] == ["ls-remote", "origin"]:
                return 0, "abc123def4567890abcdef1234567890abcdef12\n", ""
            if cmd[:2] == ["worktree", "list"]:
                return 0, "", ""
            if cmd[:3] == ["show-ref", "--verify"]:
                return 1, "", ""
            if cmd[:2] == ["worktree", "add"]:
                Path(cmd[3]).mkdir(parents=True, exist_ok=True)
                return 0, "", ""
            if cmd[:2] == ["branch", "--show-current"]:
                b = "feat/example"
                if "feat/other" in str(cwd) or "feat-other" in str(cwd):
                    b = "feat/other"
                if "bridge" in str(cwd):
                    b = "coord/bridge/a" if "pkg-a" in str(cwd) or "/a" in str(cwd) else "coord/bridge/b"
                return 0, b + "\n", ""
            if cmd[:2] == ["rev-parse", "HEAD"]:
                if "bridge" in str(cwd):
                    return 0, ("s1\n" if "bridge/a" in str(cwd) or "-a" in str(cwd) else "s2\n"), ""
                return 0, "abc123def4567890abcdef1234567890abcdef12\n", ""
            if cmd == ["rev-parse", "--is-inside-work-tree"]:
                return 0, "true\n", ""
            if cmd[:2] == ["status", "--porcelain"]:
                return 0, "", ""
            if cmd[:2] == ["remote", "get-url", "origin"]:
                return 0, "git@github.com:kkobanenko/ai-core.git\n", ""
            return 0, "", ""

        for c in candidates:
            process_candidate(
                c,
                config,
                git_runner=git_runner,
                coordinator_invoker=fake_coordinator,
            )
        assert active["max"] == 1

    def test_network_error_does_not_kill_scan(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        calls = {"n": 0}

        def git_runner(args, cwd):
            cmd = list(args)
            if cmd[:2] == ["fetch", "origin"]:
                calls["n"] += 1
                if calls["n"] == 1:
                    return 1, "", "network down"
                return 0, "", ""
            if cmd[:2] == ["for-each-ref"]:
                return 0, "", ""
            return 0, "", ""

        s1 = scan_repositories(
            config,
            git_runner=git_runner,
            coordinator_invoker=lambda **k: None,
            state_dir=state_dir,
        )
        assert s1["errors"]

        s2 = scan_repositories(
            config,
            git_runner=git_runner,
            coordinator_invoker=lambda **k: None,
            state_dir=state_dir,
        )
        assert s2["errors"] == []


class TestValidateCandidate:
    def test_reject_non_allowlisted_repo(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        prompt = _ready_prompt(config).replace(
            "target_repo: kkobanenko/ai-core",
            "target_repo: kkobanenko/evil",
        )
        _, reason = validate_candidate(prompt, config, "kkobanenko/ai-core")
        assert reason and "allowlist" in reason

    def test_map_final_status(self) -> None:
        assert map_final_status(FinalStatus.WORK_PACKAGE_SUCCESS) == "SUCCESS"
        assert map_final_status(FinalStatus.PUBLICATION_FAILED) == "PUBLICATION_FAILED"
