"""Self-update orchestration для Coordinator tooling checkout."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from tools.dev_coordinator.gitutil import (
    GitRunner,
    canonicalize_github_repo,
    default_git_runner,
    read_origin_repo,
)
from tools.dev_coordinator.locks import (
    MaintenanceGateLock,
    ProcessLock,
    UpdaterExclusionLock,
)
from tools.dev_coordinator.paths import ensure_state_layout
from tools.dev_coordinator.safety import read_worktree_snapshot
from tools.dev_coordinator.updater_config import (
    UpdaterConfig,
    default_config_path,
    load_updater_config,
)
from tools.dev_coordinator.runner_config import default_config_path as default_runner_config_path

LOGGER = logging.getLogger("dev_coordinator.updater")

SystemctlRunner = Callable[[Sequence[str]], tuple[int, str, str]]

# Post-stop HUMAN_REQUIRED причины, которые нельзя понижать до NOOP при local==remote.
_STICKY_UNCERTAIN_REASONS = frozenset(
    {
        "ff_refused",
        "post_merge_dirty",
        "post_merge_verification_failed",
    }
)

# Post-stop HUMAN_REQUIRED, для которых допустима одна bounded-попытка start при чистом git.
_RECOVERABLE_START_REASONS = frozenset({"runner_start_failed"})

# Фаза незавершённой транзакции: маркер ставится до systemctl stop.
_PENDING_UPDATE_PHASE = "stop_mutation_window"


@dataclass(frozen=True)
class UpdateOutcome:
    """Результат одной попытки self-update."""

    result: str
    reason: str
    local_head: Optional[str] = None
    remote_head: Optional[str] = None
    runner_stopped: bool = False
    runner_started: bool = False
    merge_attempted: bool = False


def updater_state_path(state_dir: Path) -> Path:
    return state_dir / "updater-state.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_updater_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": 1}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1}
    if not isinstance(data, dict):
        return {"version": 1}
    data.setdefault("version", 1)
    return data


def save_updater_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _default_systemctl(args: Sequence[str]) -> tuple[int, str, str]:
    import subprocess

    proc = subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _read_head(repo: Path, git_runner: GitRunner) -> Optional[str]:
    code, out, _ = git_runner(["rev-parse", "HEAD"], repo)
    if code != 0:
        return None
    return out.strip() or None


def _read_remote_transition_head(
    repo: Path,
    branch: str,
    git_runner: GitRunner,
) -> Optional[str]:
    ref = f"origin/{branch}"
    code, out, _ = git_runner(["rev-parse", ref], repo)
    if code != 0:
        return None
    return out.strip() or None


def _origin_matches(config: UpdaterConfig, repo: Path, git_runner: GitRunner) -> bool:
    canonical, raw = read_origin_repo(repo, git_runner=git_runner)
    expected = config.expected_origin_identity
    if canonical and canonical == expected:
        return True
    if raw and raw.strip().rstrip("/") == config.expected_origin_url.strip().rstrip("/"):
        return True
    if canonical and canonicalize_github_repo(config.expected_origin_url) == canonical:
        return True
    return False


def _is_ancestor(
    repo: Path,
    ancestor: str,
    descendant: str,
    git_runner: GitRunner,
) -> bool:
    code, _, _ = git_runner(
        ["merge-base", "--is-ancestor", ancestor, descendant],
        repo,
    )
    return code == 0


def _check_local_authority(
    config: UpdaterConfig,
    git_runner: GitRunner,
) -> tuple[bool, str, Optional[str]]:
    """Локальные проверки до git fetch (без сети)."""
    repo = config.coordinator_repo_root

    code, out, _ = git_runner(["rev-parse", "--is-inside-work-tree"], repo)
    if code != 0 or out.strip() != "true":
        return False, "not_a_git_worktree", None

    snap = read_worktree_snapshot(repo, git_runner=git_runner)
    if snap.branch != config.transition_branch:
        return False, "wrong_branch", snap.head_sha
    if snap.is_dirty:
        return False, "dirty_worktree", snap.head_sha
    if not _origin_matches(config, repo, git_runner):
        return False, "wrong_origin", snap.head_sha
    if not snap.head_sha:
        return False, "head_unavailable", None

    return True, "ok", snap.head_sha


def _check_post_fetch_preconditions(
    config: UpdaterConfig,
    git_runner: GitRunner,
    local_head: str,
    remote_head: Optional[str],
) -> tuple[bool, str]:
    """Проверки после fetch: remote head, ancestry, already-current."""
    if remote_head is None:
        return False, "remote_head_unavailable"
    if local_head == remote_head:
        return True, "already_current"
    if not _is_ancestor(repo=config.coordinator_repo_root, ancestor=local_head, descendant=remote_head, git_runner=git_runner):
        return False, "diverged"
    return True, "ok"


def _check_preconditions(
    config: UpdaterConfig,
    git_runner: GitRunner,
) -> tuple[bool, str]:
    """Полные проверки до остановки runner (локальные + remote после fetch)."""
    ok, reason, local_head = _check_local_authority(config, git_runner)
    if not ok:
        return False, reason
    assert local_head is not None

    remote_head = _read_remote_transition_head(
        config.coordinator_repo_root, config.transition_branch, git_runner
    )
    return _check_post_fetch_preconditions(config, git_runner, local_head, remote_head)


def _make_pending_update(pre_update_head: str, target_head: str) -> dict[str, str]:
    return {
        "pre_update_head": pre_update_head,
        "target_head": target_head,
        "phase": _PENDING_UPDATE_PHASE,
        "entered_at": _utc_now_iso(),
    }


def _get_pending_update(state: dict[str, Any]) -> Optional[dict[str, str]]:
    pending = state.get("pending_update")
    if not isinstance(pending, dict):
        return None
    pre = pending.get("pre_update_head")
    target = pending.get("target_head")
    if not isinstance(pre, str) or not pre or not isinstance(target, str) or not target:
        return None
    return pending


def _set_pending_update(
    state: dict[str, Any],
    pre_update_head: str,
    target_head: str,
) -> None:
    state["pending_update"] = _make_pending_update(pre_update_head, target_head)


def _clear_pending_update(state: dict[str, Any]) -> None:
    state.pop("pending_update", None)


def _is_sticky_uncertain_recovery(state: dict[str, Any]) -> bool:
    """Неразрешённое post-stop состояние с грязным/неопределённым git — только sticky."""
    return (
        state.get("last_result") == "HUMAN_REQUIRED"
        and state.get("reason") in _STICKY_UNCERTAIN_REASONS
    )


def _is_recoverable_start_failure(state: dict[str, Any]) -> bool:
    """Merge уже успешен, но runner не поднялся — можно попробовать один start."""
    return (
        state.get("last_result") == "HUMAN_REQUIRED"
        and state.get("reason") in _RECOVERABLE_START_REASONS
    )


def _heads_match_recorded_recovery(
    state: dict[str, Any],
    local_head: str,
    remote_head: str,
) -> bool:
    """Проверяем, что текущие head совпадают с зафиксированным успешным merge."""
    return (
        state.get("local_head") == local_head
        and state.get("remote_head") == remote_head
    )


def _persist_attempt(
    state_path: Path,
    state: dict[str, Any],
    outcome: UpdateOutcome,
    *,
    last_success_head: Optional[str] = None,
    last_runner_restart_at: Optional[str] = None,
    preserve_pending_update: bool = False,
    pending_snapshot: Optional[dict[str, Any]] = None,
    clear_pending_update: bool = False,
    preserve_sticky_result: bool = False,
) -> dict[str, Any]:
    saved_pending = pending_snapshot if pending_snapshot is not None else state.get("pending_update")
    saved_result = state.get("last_result")
    saved_reason = state.get("reason")
    state["local_head"] = outcome.local_head
    state["remote_head"] = outcome.remote_head
    state["last_attempt_at"] = _utc_now_iso()
    if preserve_sticky_result and saved_result and saved_reason:
        state["last_result"] = saved_result
        state["reason"] = saved_reason
    else:
        state["last_result"] = outcome.result
        state["reason"] = outcome.reason
    if last_success_head is not None:
        state["last_success_head"] = last_success_head
    if last_runner_restart_at is not None:
        state["last_runner_restart_at"] = last_runner_restart_at
    if clear_pending_update:
        _clear_pending_update(state)
    elif preserve_pending_update and saved_pending is not None:
        state["pending_update"] = saved_pending
    save_updater_state(state_path, state)
    return state


def _acquire_recovery_locks(
    state_dir: Path,
) -> tuple[Optional[MaintenanceGateLock], Optional[ProcessLock], Optional[UpdateOutcome]]:
    """Maintenance exclusive + process lock для recovery/critical section."""
    maintenance = MaintenanceGateLock(state_dir, mode="exclusive")
    if not maintenance.acquire():
        return None, None, UpdateOutcome(result="SKIPPED", reason="maintenance_held")

    process_lock = ProcessLock(state_dir)
    if not process_lock.acquire():
        maintenance.release()
        return None, None, UpdateOutcome(result="SKIPPED", reason="process_lock_held")

    return maintenance, process_lock, None


def _attempt_bounded_runner_start(
    config: UpdaterConfig,
    systemctl_runner: SystemctlRunner,
) -> tuple[bool, str, str]:
    """Одна bounded-попытка systemctl start."""
    start_code, start_out, start_err = systemctl_runner(["start", config.runner_service])
    if start_code == 0:
        return True, start_out, start_err
    return False, start_out, start_err


def _recover_pending_update(
    config: UpdaterConfig,
    state_path: Path,
    state: dict[str, Any],
    pending: dict[str, str],
    *,
    git_runner: GitRunner,
    systemctl_runner: SystemctlRunner,
) -> UpdateOutcome:
    """Детерминированное восстановление по durable pending_update маркеру."""
    repo = config.coordinator_repo_root
    pending_snapshot = dict(pending)
    pre_head = pending["pre_update_head"]
    target_head = pending["target_head"]

    ok, authority_reason, local_head = _check_local_authority(config, git_runner)
    if not ok:
        outcome = UpdateOutcome(
            result="HUMAN_REQUIRED",
            reason=authority_reason,
            local_head=local_head,
            remote_head=target_head,
        )
        _persist_attempt(
            state_path,
            state,
            outcome,
            preserve_pending_update=True,
            pending_snapshot=pending_snapshot,
        )
        LOGGER.warning("pending recovery blocked by authority: %s", authority_reason)
        return outcome

    assert local_head is not None

    if local_head == target_head:
        recovery_reason = "pending_merge_completed"
    elif local_head == pre_head:
        recovery_reason = "pending_pre_merge"
    else:
        outcome = UpdateOutcome(
            result="HUMAN_REQUIRED",
            reason="pending_unexpected_head",
            local_head=local_head,
            remote_head=target_head,
        )
        _persist_attempt(
            state_path,
            state,
            outcome,
            preserve_pending_update=True,
            pending_snapshot=pending_snapshot,
        )
        LOGGER.warning(
            "pending recovery: unexpected head %s (pre=%s target=%s)",
            local_head,
            pre_head,
            target_head,
        )
        return outcome

    maintenance: Optional[MaintenanceGateLock] = None
    process_lock: Optional[ProcessLock] = None
    try:
        maintenance, process_lock, skip_outcome = _acquire_recovery_locks(config.state_dir.resolve())
        if skip_outcome is not None:
            skip_outcome.local_head = local_head
            skip_outcome.remote_head = target_head
            _persist_attempt(
                state_path,
                state,
                skip_outcome,
                preserve_pending_update=True,
                pending_snapshot=pending_snapshot,
                preserve_sticky_result=True,
            )
            LOGGER.info("pending recovery skipped: %s", skip_outcome.reason)
            return skip_outcome

        ok_after_lock, lock_reason, locked_head = _check_local_authority(config, git_runner)
        if not ok_after_lock or locked_head != local_head:
            reason = lock_reason if not ok_after_lock else "pending_authority_changed"
            outcome = UpdateOutcome(
                result="HUMAN_REQUIRED",
                reason=reason,
                local_head=locked_head or local_head,
                remote_head=target_head,
            )
            _persist_attempt(
                state_path,
                state,
                outcome,
                preserve_pending_update=True,
                pending_snapshot=pending_snapshot,
            )
            return outcome

        started, start_out, start_err = _attempt_bounded_runner_start(config, systemctl_runner)
        if started:
            restart_at = _utc_now_iso()
            if recovery_reason == "pending_merge_completed":
                outcome = UpdateOutcome(
                    result="SUCCESS",
                    reason="pending_merge_recovered",
                    local_head=local_head,
                    remote_head=target_head,
                    runner_started=True,
                )
                _persist_attempt(
                    state_path,
                    state,
                    outcome,
                    last_success_head=local_head,
                    last_runner_restart_at=restart_at,
                    clear_pending_update=True,
                )
                LOGGER.info("pending recovery: merge completed, runner restarted")
                return outcome

            outcome = UpdateOutcome(
                result="FAIL_CLOSED",
                reason="pending_pre_merge_recovered",
                local_head=local_head,
                remote_head=target_head,
                runner_started=True,
            )
            _persist_attempt(
                state_path,
                state,
                outcome,
                last_runner_restart_at=restart_at,
                clear_pending_update=True,
            )
            LOGGER.info("pending recovery: pre-merge state, runner restored")
            return outcome

        outcome = UpdateOutcome(
            result="HUMAN_REQUIRED",
            reason="runner_start_failed",
            local_head=local_head,
            remote_head=target_head,
            runner_started=False,
        )
        _persist_attempt(
            state_path,
            state,
            outcome,
            preserve_pending_update=True,
            pending_snapshot=pending_snapshot,
        )
        LOGGER.error("pending recovery start failed: %s", start_err or start_out)
        return outcome
    finally:
        if process_lock is not None:
            process_lock.release()
        if maintenance is not None:
            maintenance.release()


def _recover_legacy_runner_start_failure(
    config: UpdaterConfig,
    state_path: Path,
    state: dict[str, Any],
    local_head: str,
    remote_head: str,
    *,
    git_runner: GitRunner,
    systemctl_runner: SystemctlRunner,
) -> UpdateOutcome:
    """Обратная совместимость: recovery по last_result без pending_update."""
    pending_snapshot = state.get("pending_update")

    if not _heads_match_recorded_recovery(state, local_head, remote_head):
        outcome = UpdateOutcome(
            result="HUMAN_REQUIRED",
            reason="runner_start_failed",
            local_head=local_head,
            remote_head=remote_head,
        )
        _persist_attempt(
            state_path,
            state,
            outcome,
            preserve_pending_update=pending_snapshot is not None,
            pending_snapshot=pending_snapshot,
        )
        LOGGER.warning("runner_start_failed sticky: heads no longer match recorded merge")
        return outcome

    maintenance: Optional[MaintenanceGateLock] = None
    process_lock: Optional[ProcessLock] = None
    try:
        maintenance, process_lock, skip_outcome = _acquire_recovery_locks(config.state_dir.resolve())
        if skip_outcome is not None:
            skip_outcome.local_head = local_head
            skip_outcome.remote_head = remote_head
            _persist_attempt(
                state_path,
                state,
                skip_outcome,
                preserve_pending_update=True,
                pending_snapshot=pending_snapshot,
                preserve_sticky_result=True,
            )
            LOGGER.info("runner recovery skipped: %s", skip_outcome.reason)
            return skip_outcome

        ok, reason = _check_preconditions(config, git_runner)
        if ok and reason == "already_current":
            started, start_out, start_err = _attempt_bounded_runner_start(config, systemctl_runner)
            if started:
                restart_at = _utc_now_iso()
                outcome = UpdateOutcome(
                    result="SUCCESS",
                    reason="runner_start_recovered",
                    local_head=local_head,
                    remote_head=remote_head,
                    runner_started=True,
                )
                _persist_attempt(
                    state_path,
                    state,
                    outcome,
                    last_success_head=local_head,
                    last_runner_restart_at=restart_at,
                    clear_pending_update=True,
                )
                LOGGER.info("runner recovery succeeded after prior start failure")
                return outcome

            outcome = UpdateOutcome(
                result="HUMAN_REQUIRED",
                reason="runner_start_failed",
                local_head=local_head,
                remote_head=remote_head,
                runner_started=False,
            )
            _persist_attempt(
                state_path,
                state,
                outcome,
                preserve_pending_update=True,
                pending_snapshot=pending_snapshot,
            )
            LOGGER.error("runner recovery start failed: %s", start_err or start_out)
            return outcome

        outcome = UpdateOutcome(
            result="HUMAN_REQUIRED",
            reason="runner_start_failed",
            local_head=local_head,
            remote_head=remote_head,
        )
        _persist_attempt(
            state_path,
            state,
            outcome,
            preserve_pending_update=True,
            pending_snapshot=pending_snapshot,
        )
        LOGGER.warning("runner recovery blocked by preconditions: %s", reason)
        return outcome
    finally:
        if process_lock is not None:
            process_lock.release()
        if maintenance is not None:
            maintenance.release()


def run_update_once(
    config: UpdaterConfig,
    *,
    git_runner: GitRunner = default_git_runner,
    systemctl_runner: SystemctlRunner = _default_systemctl,
) -> UpdateOutcome:
    """Одна детерминированная попытка self-update."""
    state_dir = config.state_dir.resolve()
    ensure_state_layout(state_dir)
    state_path = updater_state_path(state_dir)
    state = load_updater_state(state_path)
    repo = config.coordinator_repo_root

    exclusion = UpdaterExclusionLock(state_dir)
    if not exclusion.acquire():
        outcome = UpdateOutcome(
            result="SKIPPED",
            reason="updater_busy",
        )
        _persist_attempt(state_path, state, outcome)
        LOGGER.info("updater skipped: %s", outcome.reason)
        return outcome

    maintenance: Optional[MaintenanceGateLock] = None
    process_lock: Optional[ProcessLock] = None
    pre_stop_snapshot: Optional[tuple[str, bool]] = None
    runner_stopped = False
    runner_started = False
    merge_attempted = False

    try:
        # Шаг 1: durable pending_update recovery (до fetch, без сети).
        pending = _get_pending_update(state)
        if pending is not None:
            return _recover_pending_update(
                config,
                state_path,
                state,
                pending,
                git_runner=git_runner,
                systemctl_runner=systemctl_runner,
            )

        # Шаг 2: локальный authority gate до git fetch.
        authority_ok, authority_reason, local_head = _check_local_authority(
            config, git_runner
        )
        if not authority_ok:
            outcome = UpdateOutcome(
                result="FAIL_CLOSED",
                reason=authority_reason,
                local_head=local_head,
                remote_head=None,
            )
            _persist_attempt(state_path, state, outcome)
            LOGGER.info("updater authority gate failed: %s", authority_reason)
            return outcome

        assert local_head is not None

        # Шаг 3: fetch origin only (после authority gate).
        code, out, err = git_runner(["fetch", "origin"], repo)
        if code != 0:
            outcome = UpdateOutcome(
                result="FAIL_CLOSED",
                reason="fetch_error",
                local_head=local_head,
                remote_head=None,
            )
            _persist_attempt(state_path, state, outcome)
            LOGGER.warning("git fetch origin failed: %s", err or out)
            return outcome

        remote_head = _read_remote_transition_head(
            repo, config.transition_branch, git_runner
        )

        # Шаг 4: local==remote — NOOP или sticky/recovery post-stop пути.
        if local_head and remote_head and local_head == remote_head:
            if _is_sticky_uncertain_recovery(state):
                prior_reason = str(state.get("reason", "unknown"))
                outcome = UpdateOutcome(
                    result="HUMAN_REQUIRED",
                    reason=prior_reason,
                    local_head=local_head,
                    remote_head=remote_head,
                )
                _persist_attempt(state_path, state, outcome)
                LOGGER.warning(
                    "updater sticky recovery preserved: %s", prior_reason
                )
                return outcome

            if _is_recoverable_start_failure(state):
                return _recover_legacy_runner_start_failure(
                    config,
                    state_path,
                    state,
                    local_head,
                    remote_head,
                    git_runner=git_runner,
                    systemctl_runner=systemctl_runner,
                )

            outcome = UpdateOutcome(
                result="NOOP",
                reason="already_current",
                local_head=local_head,
                remote_head=remote_head,
            )
            _persist_attempt(state_path, state, outcome)
            LOGGER.info("updater noop: already at remote head")
            return outcome

        # Шаг 5: post-fetch preconditions (diverged, remote unavailable).
        post_ok, post_reason = _check_post_fetch_preconditions(
            config, git_runner, local_head, remote_head
        )
        if not post_ok:
            outcome = UpdateOutcome(
                result="FAIL_CLOSED",
                reason=post_reason,
                local_head=local_head,
                remote_head=remote_head,
            )
            _persist_attempt(state_path, state, outcome)
            LOGGER.info("updater post-fetch preconditions failed: %s", post_reason)
            return outcome

        # Шаг 6: maintenance exclusive.
        maintenance = MaintenanceGateLock(state_dir, mode="exclusive")
        if not maintenance.acquire():
            outcome = UpdateOutcome(
                result="SKIPPED",
                reason="maintenance_held",
                local_head=local_head,
                remote_head=remote_head,
            )
            _persist_attempt(state_path, state, outcome)
            LOGGER.info("updater skipped: maintenance held by runner")
            return outcome

        # Шаг 7: Coordinator process lock.
        process_lock = ProcessLock(state_dir)
        if not process_lock.acquire():
            maintenance.release()
            maintenance = None
            outcome = UpdateOutcome(
                result="SKIPPED",
                reason="process_lock_held",
                local_head=local_head,
                remote_head=remote_head,
            )
            _persist_attempt(state_path, state, outcome)
            LOGGER.info("updater skipped: coordinator process lock held")
            return outcome

        # Шаг 8: полные preconditions (пока оба lock удерживаются).
        ok, reason = _check_preconditions(config, git_runner)
        if not ok:
            result = "NOOP" if reason == "already_current" else "FAIL_CLOSED"
            outcome = UpdateOutcome(
                result=result,
                reason=reason,
                local_head=local_head,
                remote_head=remote_head,
            )
            _persist_attempt(state_path, state, outcome)
            LOGGER.info("updater preconditions failed: %s", reason)
            return outcome

        snap = read_worktree_snapshot(repo, git_runner=git_runner)
        pre_stop_snapshot = (snap.head_sha or "", not snap.is_dirty)
        assert remote_head is not None

        # Шаг 9: durable pending_update маркер ДО systemctl stop.
        _set_pending_update(state, snap.head_sha or local_head, remote_head)
        save_updater_state(state_path, state)

        # Шаг 10: stop runner.
        stop_code, stop_out, stop_err = systemctl_runner(
            ["stop", config.runner_service]
        )
        if stop_code != 0:
            outcome = UpdateOutcome(
                result="FAIL_CLOSED",
                reason="runner_stop_failed",
                local_head=local_head,
                remote_head=remote_head,
            )
            _persist_attempt(
                state_path,
                state,
                outcome,
                preserve_pending_update=True,
            )
            LOGGER.warning(
                "systemctl stop failed: %s", stop_err or stop_out
            )
            return outcome
        runner_stopped = True

        # Шаг 11: единственная git-мутация — ff-only merge.
        merge_ref = f"origin/{config.transition_branch}"
        merge_attempted = True
        merge_code, merge_out, merge_err = git_runner(
            ["merge", "--ff-only", merge_ref],
            repo,
        )

        new_head = _read_head(repo, git_runner)
        post_snap = read_worktree_snapshot(repo, git_runner=git_runner)

        if merge_code != 0:
            # Post-stop failure policy.
            unchanged = (
                pre_stop_snapshot is not None
                and new_head == pre_stop_snapshot[0]
                and not post_snap.is_dirty
                and pre_stop_snapshot[1]
            )
            if unchanged:
                start_code, start_out, start_err = systemctl_runner(
                    ["start", config.runner_service]
                )
                if start_code == 0:
                    runner_started = True
                outcome = UpdateOutcome(
                    result="FAIL_CLOSED",
                    reason="ff_refused_recoverable",
                    local_head=new_head,
                    remote_head=remote_head,
                    runner_stopped=runner_stopped,
                    runner_started=runner_started,
                    merge_attempted=True,
                )
                restart_at = _utc_now_iso() if runner_started else None
                _persist_attempt(
                    state_path,
                    state,
                    outcome,
                    last_runner_restart_at=restart_at,
                    clear_pending_update=True,
                )
                LOGGER.warning(
                    "ff-only refused but worktree unchanged; runner restore attempted"
                )
                return outcome

            outcome = UpdateOutcome(
                result="HUMAN_REQUIRED",
                reason="ff_refused",
                local_head=new_head,
                remote_head=remote_head,
                runner_stopped=runner_stopped,
                runner_started=False,
                merge_attempted=True,
            )
            _persist_attempt(
                state_path,
                state,
                outcome,
                preserve_pending_update=True,
            )
            LOGGER.error("ff-only refused with uncertain state; runner left stopped")
            return outcome

        # Шаг 12: verify HEAD == remote и worktree clean.
        if not new_head or remote_head is None or new_head != remote_head:
            outcome = UpdateOutcome(
                result="HUMAN_REQUIRED",
                reason="post_merge_verification_failed",
                local_head=new_head,
                remote_head=remote_head,
                runner_stopped=runner_stopped,
                merge_attempted=True,
            )
            _persist_attempt(
                state_path,
                state,
                outcome,
                preserve_pending_update=True,
            )
            return outcome
        if post_snap.is_dirty:
            outcome = UpdateOutcome(
                result="HUMAN_REQUIRED",
                reason="post_merge_dirty",
                local_head=new_head,
                remote_head=remote_head,
                runner_stopped=runner_stopped,
                merge_attempted=True,
            )
            _persist_attempt(
                state_path,
                state,
                outcome,
                preserve_pending_update=True,
            )
            return outcome

        # Шаг 13: start runner exactly once on success.
        start_code, start_out, start_err = systemctl_runner(
            ["start", config.runner_service]
        )
        if start_code != 0:
            outcome = UpdateOutcome(
                result="HUMAN_REQUIRED",
                reason="runner_start_failed",
                local_head=new_head,
                remote_head=remote_head,
                runner_stopped=runner_stopped,
                runner_started=False,
                merge_attempted=True,
            )
            _persist_attempt(
                state_path,
                state,
                outcome,
                preserve_pending_update=True,
            )
            LOGGER.error("runner start failed after successful merge")
            return outcome

        runner_started = True
        restart_at = _utc_now_iso()
        outcome = UpdateOutcome(
            result="SUCCESS",
            reason="ff_only_merge",
            local_head=new_head,
            remote_head=remote_head,
            runner_stopped=runner_stopped,
            runner_started=runner_started,
            merge_attempted=True,
        )
        _persist_attempt(
            state_path,
            state,
            outcome,
            last_success_head=new_head,
            last_runner_restart_at=restart_at,
            clear_pending_update=True,
        )
        LOGGER.info("updater success: head=%s", new_head)
        return outcome

    finally:
        if process_lock is not None:
            process_lock.release()
        if maintenance is not None:
            maintenance.release()
        exclusion.release()


def build_status_report(
    config: UpdaterConfig,
    state_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Read-only статус updater."""
    path = state_path or updater_state_path(config.state_dir)
    state = load_updater_state(path)
    return {
        "config_path": str(default_config_path()),
        "state_path": str(path),
        "coordinator_repo_root": str(config.coordinator_repo_root),
        "transition_branch": config.transition_branch,
        "runner_service": config.runner_service,
        "timer_interval_seconds": config.timer_interval_seconds,
        "local_head": state.get("local_head"),
        "remote_head": state.get("remote_head"),
        "last_attempt_at": state.get("last_attempt_at"),
        "last_result": state.get("last_result"),
        "reason": state.get("reason"),
        "last_success_head": state.get("last_success_head"),
        "last_runner_restart_at": state.get("last_runner_restart_at"),
        "pending_update": state.get("pending_update"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dev_coordinator.updater",
        description="Coordinator tooling self-update (ff-only, fail-closed).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to updater.json (default: XDG config path)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single update attempt and exit",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print read-only status and exit",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output for --status or --once",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable INFO logging",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    config_path = (args.config or default_config_path()).resolve()
    try:
        config = load_updater_config(
            config_path,
            runner_config_path=default_runner_config_path(),
        )
    except (OSError, ValueError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if args.status:
        report = build_status_report(config)
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(f"state_path: {report['state_path']}")
            print(f"local_head: {report['local_head']}")
            print(f"remote_head: {report['remote_head']}")
            print(f"last_result: {report['last_result']}")
            print(f"reason: {report['reason']}")
            print(f"last_attempt_at: {report['last_attempt_at']}")
            if report.get("pending_update"):
                print(f"pending_update: {report['pending_update']}")
        return 0

    if not args.once:
        parser.error("--once or --status is required")

    outcome = run_update_once(config)
    payload = {
        "result": outcome.result,
        "reason": outcome.reason,
        "local_head": outcome.local_head,
        "remote_head": outcome.remote_head,
        "runner_stopped": outcome.runner_stopped,
        "runner_started": outcome.runner_started,
        "merge_attempted": outcome.merge_attempted,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(
            f"UPDATE result={outcome.result} reason={outcome.reason} "
            f"local={outcome.local_head} remote={outcome.remote_head}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
