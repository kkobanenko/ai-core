"""Тесты self-update updater (fake git/systemctl/locks only)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Optional

import pytest

from tools.dev_coordinator.locks import (
    MaintenanceGateLock,
    ProcessLock,
    UpdaterExclusionLock,
)
from tools.dev_coordinator.runner import scan_with_maintenance_gate
from tools.dev_coordinator.runner_config import parse_runner_config
from tools.dev_coordinator.updater import (
    build_status_report,
    load_updater_state,
    run_update_once,
    save_updater_state,
    updater_state_path,
)
from tools.dev_coordinator.updater_config import (
    UpdaterConfig,
    parse_updater_config,
    validate_against_runner_config,
)


def _layout(tmp_path: Path) -> dict[str, Path]:
    coord = tmp_path / "coord"
    state = tmp_path / "state"
    coord.mkdir()
    state.mkdir()
    return {"coord": coord, "state": state}


def _updater_config(paths: dict[str, Path], **overrides: Any) -> UpdaterConfig:
    data = {
        "coordinator_repo_root": str(paths["coord"]),
        "transition_branch": "chore/coordinator-transition-v0.1-20260911",
        "expected_origin_url": "https://github.com/kkobanenko/ai-core.git",
        "runner_service": "ai-core-dev-coordinator-runner.service",
        "timer_interval_seconds": 60,
        "state_dir": str(paths["state"]),
    }
    data.update(overrides)
    return parse_updater_config(data)


class FakeGitRepo:
    """Минимальная in-memory модель git checkout для updater."""

    def __init__(
        self,
        *,
        branch: str = "chore/coordinator-transition-v0.1-20260911",
        head: str = "local_head_1",
        remote_head: str = "local_head_1",
        dirty: bool = False,
        origin: str = "https://github.com/kkobanenko/ai-core.git",
        diverged: bool = False,
        allow_ff: bool = True,
    ) -> None:
        self.branch = branch
        self.head = head
        self.remote_head = remote_head
        self.dirty = dirty
        self.origin = origin
        self.diverged = diverged
        self.allow_ff = allow_ff
        self.commands: list[list[str]] = []

    def runner(self, args, cwd):
        cmd = list(args)
        self.commands.append(cmd)
        if cmd == ["fetch", "origin"]:
            return 0, "", ""
        if cmd == ["rev-parse", "HEAD"]:
            return 0, self.head + "\n", ""
        if cmd[:1] == ["rev-parse"] and cmd[1].startswith("origin/"):
            return 0, self.remote_head + "\n", ""
        if cmd == ["rev-parse", "--is-inside-work-tree"]:
            return 0, "true\n", ""
        if cmd[:2] == ["branch", "--show-current"]:
            return 0, self.branch + "\n", ""
        if cmd[:2] == ["status", "--porcelain"]:
            if self.dirty:
                return 0, " M dirty.txt\n", ""
            return 0, "", ""
        if cmd[:3] == ["remote", "get-url", "origin"]:
            return 0, self.origin + "\n", ""
        if cmd[:2] == ["merge-base", "--is-ancestor"]:
            if self.diverged:
                return 1, "", ""
            return 0, "", ""
        if cmd[:2] == ["merge", "--ff-only"]:
            if not self.allow_ff:
                return 1, "", "fatal: Not possible to fast-forward"
            self.head = self.remote_head
            return 0, "", ""
        return 0, "", ""


class TestUpdaterConfig:
    def test_valid_config(self, tmp_path: Path) -> None:
        cfg = _updater_config(_layout(tmp_path))
        assert cfg.timer_interval_seconds == 60
        assert cfg.expected_origin_identity == "kkobanenko/ai-core"

    def test_reject_unknown_key(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        data = {
            "coordinator_repo_root": str(paths["coord"]),
            "transition_branch": "chore/coordinator-transition-v0.1-20260911",
            "expected_origin_url": "https://github.com/kkobanenko/ai-core.git",
            "runner_service": "ai-core-dev-coordinator-runner.service",
            "timer_interval_seconds": 60,
            "state_dir": str(paths["state"]),
            "extra": True,
        }
        with pytest.raises(ValueError, match="unknown config keys"):
            parse_updater_config(data)

    @pytest.mark.parametrize(
        "field,value,match",
        [
            ("transition_branch", "", "non-empty"),
            ("transition_branch", "main", "must not be"),
            ("transition_branch", "master", "must not be"),
            ("expected_origin_url", "", "non-empty"),
            ("timer_interval_seconds", 20, "timer_interval_seconds"),
            ("coordinator_repo_root", "relative/coord", "absolute path"),
            ("state_dir", "relative/state", "absolute path"),
        ],
    )
    def test_reject_invalid_values(
        self, tmp_path: Path, field: str, value: object, match: str
    ) -> None:
        paths = _layout(tmp_path)
        data = {
            "coordinator_repo_root": str(paths["coord"]),
            "transition_branch": "chore/coordinator-transition-v0.1-20260911",
            "expected_origin_url": "https://github.com/kkobanenko/ai-core.git",
            "runner_service": "ai-core-dev-coordinator-runner.service",
            "timer_interval_seconds": 60,
            "state_dir": str(paths["state"]),
        }
        data[field] = value
        with pytest.raises(ValueError, match=match):
            parse_updater_config(data)

    def test_runner_config_mismatch(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        other = tmp_path / "other-coord"
        other.mkdir()
        updater = _updater_config(paths)
        runner_path = tmp_path / "runner.json"
        runner_path.write_text(
            json.dumps(
                {
                    "poll_interval_seconds": 15,
                    "coordinator_repo_root": str(other),
                    "managed_worktree_root": str(tmp_path / "wt"),
                    "agent_bin": str(tmp_path / "agent"),
                    "bridge_prefix": "coord/bridge/",
                    "repositories": {"kkobanenko/ai-core": str(tmp_path / "clone")},
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "wt").mkdir()
        (tmp_path / "clone").mkdir()
        agent = tmp_path / "agent"
        agent.write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match="mismatch"):
            validate_against_runner_config(updater, runner_path)


class TestUpdaterOrchestration:
    def _systemctl_recorder(self) -> tuple[list[list[str]], Any]:
        calls: list[list[str]] = []

        def runner(args):
            calls.append(list(args))
            return 0, "", ""

        return calls, runner

    def test_noop_already_current(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(head="same", remote_head="same")
        calls, systemctl = self._systemctl_recorder()

        outcome = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "NOOP"
        assert outcome.runner_stopped is False
        assert outcome.runner_started is False
        assert calls == []
        assert ["fetch", "origin"] in fake.commands

    def test_success_ff_only(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(head="old", remote_head="new")
        calls, systemctl = self._systemctl_recorder()

        outcome = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "SUCCESS"
        assert calls == [
            ["stop", "ai-core-dev-coordinator-runner.service"],
            ["start", "ai-core-dev-coordinator-runner.service"],
        ]
        assert fake.commands.count(["merge", "--ff-only", f"origin/{fake.branch}"]) == 1

    def test_dirty_refuses_without_stop(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(head="old", remote_head="new", dirty=True)
        calls, systemctl = self._systemctl_recorder()

        outcome = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "FAIL_CLOSED"
        assert outcome.reason == "dirty_worktree"
        assert calls == []

    def test_diverged_refuses_without_stop(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(head="old", remote_head="new", diverged=True)
        calls, systemctl = self._systemctl_recorder()

        outcome = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "FAIL_CLOSED"
        assert outcome.reason == "diverged"
        assert calls == []

    def test_wrong_branch_refuses(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(
            branch="feat/wrong",
            head="old",
            remote_head="new",
        )
        calls, systemctl = self._systemctl_recorder()

        outcome = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "FAIL_CLOSED"
        assert outcome.reason == "wrong_branch"
        assert calls == []

    def test_wrong_origin_refuses(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(
            head="old",
            remote_head="new",
            origin="https://github.com/kkobanenko/evil.git",
        )
        calls, systemctl = self._systemctl_recorder()

        outcome = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "FAIL_CLOSED"
        assert outcome.reason == "wrong_origin"
        assert calls == []

    def test_fetch_failure_no_mutation(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)

        def git_runner(args, cwd):
            if list(args) == ["fetch", "origin"]:
                return 1, "", "network down"
            raise AssertionError(f"unexpected: {args}")

        calls, systemctl = self._systemctl_recorder()
        outcome = run_update_once(
            config,
            git_runner=git_runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "FAIL_CLOSED"
        assert outcome.reason == "fetch_error"
        assert calls == []

    def test_systemctl_stop_failure_no_merge(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(head="old", remote_head="new")

        def systemctl(args):
            if list(args)[:1] == ["stop"]:
                return 1, "", "stop failed"
            return 0, "", ""

        outcome = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "FAIL_CLOSED"
        assert outcome.reason == "runner_stop_failed"
        assert not any(c[:2] == ["merge", "--ff-only"] for c in fake.commands)

    def test_ff_failure_recoverable(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(head="old", remote_head="new", allow_ff=False)
        calls, systemctl = self._systemctl_recorder()

        outcome = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "FAIL_CLOSED"
        assert outcome.reason == "ff_refused_recoverable"
        assert calls == [
            ["stop", "ai-core-dev-coordinator-runner.service"],
            ["start", "ai-core-dev-coordinator-runner.service"],
        ]

    def test_ff_failure_uncertain_human_required(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(head="old", remote_head="new", allow_ff=False)

        def git_runner(args, cwd):
            cmd = list(args)
            fake.commands.append(cmd)
            if cmd[:2] == ["merge", "--ff-only"]:
                fake.dirty = True
                return 1, "", "fatal: Not possible to fast-forward"
            return fake.runner(args, cwd)

        calls, systemctl = self._systemctl_recorder()
        outcome = run_update_once(
            config,
            git_runner=git_runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "HUMAN_REQUIRED"
        assert outcome.reason == "ff_refused"
        assert calls == [["stop", "ai-core-dev-coordinator-runner.service"]]

    def test_start_failure_after_merge(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(head="old", remote_head="new")

        def systemctl(args):
            if list(args)[:1] == ["start"]:
                return 1, "", "start failed"
            return 0, "", ""

        outcome = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "HUMAN_REQUIRED"
        assert outcome.reason == "runner_start_failed"

    def test_state_persistence(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(head="same", remote_head="same")
        _, systemctl = self._systemctl_recorder()

        run_update_once(config, git_runner=fake.runner, systemctl_runner=systemctl)
        state = load_updater_state(updater_state_path(paths["state"]))
        assert state["last_result"] == "NOOP"
        assert state["reason"] == "already_current"
        report = build_status_report(config)
        assert report["last_result"] == "NOOP"


class TestUpdaterStickyRecovery:
    """Consecutive attempts: sticky post-stop HUMAN_REQUIRED must not downgrade to NOOP."""

    def test_runner_start_failed_then_recovery_succeeds(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(head="old", remote_head="new")
        start_calls = 0

        def systemctl(args):
            nonlocal start_calls
            if list(args)[:1] == ["start"]:
                start_calls += 1
                if start_calls == 1:
                    return 1, "", "start failed"
                return 0, "", ""
            return 0, "", ""

        first = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert first.result == "HUMAN_REQUIRED"
        assert first.reason == "runner_start_failed"
        assert fake.head == "new"

        merge_count_before = fake.commands.count(
            ["merge", "--ff-only", f"origin/{fake.branch}"]
        )
        second = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert second.result == "SUCCESS"
        assert second.reason == "runner_start_recovered"
        assert second.runner_started is True
        assert second.merge_attempted is False
        assert fake.commands.count(
            ["merge", "--ff-only", f"origin/{fake.branch}"]
        ) == merge_count_before
        assert start_calls == 2

        state = load_updater_state(updater_state_path(paths["state"]))
        assert state["last_result"] == "SUCCESS"
        assert state["reason"] == "runner_start_recovered"

    def test_runner_start_failed_stays_sticky_when_recovery_fails(
        self, tmp_path: Path
    ) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(head="old", remote_head="new")

        def systemctl(args):
            if list(args)[:1] == ["start"]:
                return 1, "", "start failed"
            return 0, "", ""

        first = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert first.result == "HUMAN_REQUIRED"
        assert first.reason == "runner_start_failed"

        merge_count_before = fake.commands.count(
            ["merge", "--ff-only", f"origin/{fake.branch}"]
        )
        second = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert second.result == "HUMAN_REQUIRED"
        assert second.reason == "runner_start_failed"
        assert second.merge_attempted is False
        assert fake.commands.count(
            ["merge", "--ff-only", f"origin/{fake.branch}"]
        ) == merge_count_before

    def test_already_current_without_recovery_is_noop(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(head="same", remote_head="same")
        calls, systemctl = TestUpdaterOrchestration()._systemctl_recorder()

        outcome = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "NOOP"
        assert outcome.reason == "already_current"
        assert calls == []

    @pytest.mark.parametrize(
        "sticky_reason",
        ["ff_refused", "post_merge_dirty", "post_merge_verification_failed"],
    )
    def test_sticky_uncertain_not_cleared_by_already_current(
        self, tmp_path: Path, sticky_reason: str
    ) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(head="merged_head", remote_head="merged_head")
        state_path = updater_state_path(paths["state"])
        save_updater_state(
            state_path,
            {
                "version": 1,
                "local_head": "merged_head",
                "remote_head": "merged_head",
                "last_result": "HUMAN_REQUIRED",
                "reason": sticky_reason,
            },
        )
        calls, systemctl = TestUpdaterOrchestration()._systemctl_recorder()

        outcome = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "HUMAN_REQUIRED"
        assert outcome.reason == sticky_reason
        assert calls == []
        assert not any(c[:2] == ["merge", "--ff-only"] for c in fake.commands)

        state = load_updater_state(state_path)
        assert state["last_result"] == "HUMAN_REQUIRED"
        assert state["reason"] == sticky_reason


class TestUpdaterLocks:
    def test_runner_skips_when_updater_holds_exclusive(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        managed = tmp_path / "wt"
        agent = tmp_path / "agent"
        clone = tmp_path / "clone"
        for d in (managed, clone):
            d.mkdir()
        agent.write_text("x", encoding="utf-8")
        config = parse_runner_config(
            {
                "poll_interval_seconds": 15,
                "coordinator_repo_root": str(paths["coord"]),
                "managed_worktree_root": str(managed),
                "agent_bin": str(agent),
                "bridge_prefix": "coord/bridge/",
                "repositories": {"kkobanenko/ai-core": str(clone)},
            }
        )

        exclusive = MaintenanceGateLock(paths["state"], mode="exclusive")
        assert exclusive.acquire()

        summary = scan_with_maintenance_gate(
            config,
            git_runner=lambda *a, **k: (0, "", ""),
            state_dir=paths["state"],
        )
        assert summary["skipped"] is True
        assert summary["skip_reason"] == "maintenance_held"
        assert summary["candidates_found"] == 0
        exclusive.release()

    def test_updater_skips_when_runner_holds_shared(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        shared = MaintenanceGateLock(paths["state"], mode="shared")
        assert shared.acquire()

        fake = FakeGitRepo(head="old", remote_head="new")
        calls: list[list[str]] = []

        def systemctl(args):
            calls.append(list(args))
            return 0, "", ""

        outcome = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "SKIPPED"
        assert outcome.reason == "maintenance_held"
        assert calls == []
        shared.release()

    def test_updater_holds_process_lock_during_critical_section(
        self, tmp_path: Path
    ) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        fake = FakeGitRepo(head="old", remote_head="new")
        held_during_merge = {"ok": False}

        original_runner = fake.runner

        def git_runner(args, cwd):
            cmd = list(args)
            if cmd[:2] == ["merge", "--ff-only"]:
                lock = ProcessLock(paths["state"])
                held_during_merge["ok"] = lock.acquire() is False
            return original_runner(args, cwd)

        calls: list[list[str]] = []

        def systemctl(args):
            calls.append(list(args))
            return 0, "", ""

        outcome = run_update_once(
            config,
            git_runner=git_runner,
            systemctl_runner=systemctl,
        )
        assert outcome.result == "SUCCESS"
        assert held_during_merge["ok"] is True

    def test_concurrent_lock_ordering_no_deadlock(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        config = _updater_config(paths)
        errors: list[str] = []

        def updater_thread() -> None:
            try:
                fake = FakeGitRepo(head="old", remote_head="new")
                run_update_once(
                    config,
                    git_runner=fake.runner,
                    systemctl_runner=lambda a: (0, "", ""),
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"updater: {exc}")

        def runner_thread() -> None:
            try:
                managed = tmp_path / "wt2"
                agent = tmp_path / "agent2"
                clone = tmp_path / "clone2"
                for d in (managed, clone):
                    d.mkdir(exist_ok=True)
                agent.write_text("x", encoding="utf-8")
                cfg = parse_runner_config(
                    {
                        "poll_interval_seconds": 15,
                        "coordinator_repo_root": str(paths["coord"]),
                        "managed_worktree_root": str(managed),
                        "agent_bin": str(agent),
                        "bridge_prefix": "coord/bridge/",
                        "repositories": {"kkobanenko/ai-core": str(clone)},
                    }
                )
                scan_with_maintenance_gate(
                    cfg,
                    git_runner=lambda *a, **k: (0, "", ""),
                    state_dir=paths["state"],
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"runner: {exc}")

        threads = [
            threading.Thread(target=updater_thread),
            threading.Thread(target=runner_thread),
            threading.Thread(target=updater_thread),
            threading.Thread(target=runner_thread),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
            assert not t.is_alive()

        assert errors == []

    def test_updater_exclusion_prevents_concurrent_runs(self, tmp_path: Path) -> None:
        paths = _layout(tmp_path)
        lock = UpdaterExclusionLock(paths["state"])
        assert lock.acquire()
        config = _updater_config(paths)
        fake = FakeGitRepo(head="same", remote_head="same")
        outcome = run_update_once(
            config,
            git_runner=fake.runner,
            systemctl_runner=lambda a: (0, "", ""),
        )
        assert outcome.result == "SKIPPED"
        assert outcome.reason == "updater_busy"
        lock.release()
