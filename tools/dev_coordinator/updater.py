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


def _check_preconditions(
    config: UpdaterConfig,
    git_runner: GitRunner,
) -> tuple[bool, str]:
    """Проверки до остановки runner."""
    repo = config.coordinator_repo_root

    code, out, _ = git_runner(["rev-parse", "--is-inside-work-tree"], repo)
    if code != 0 or out.strip() != "true":
        return False, "not_a_git_worktree"

    snap = read_worktree_snapshot(repo, git_runner=git_runner)
    if snap.branch != config.transition_branch:
        return False, "wrong_branch"
    if snap.is_dirty:
        return False, "dirty_worktree"
    if not _origin_matches(config, repo, git_runner):
        return False, "wrong_origin"
    if not snap.head_sha:
        return False, "head_unavailable"

    remote_head = _read_remote_transition_head(repo, config.transition_branch, git_runner)
    if remote_head is None:
        return False, "remote_head_unavailable"
    if snap.head_sha == remote_head:
        return True, "already_current"
    if not _is_ancestor(repo, snap.head_sha, remote_head, git_runner):
        return False, "diverged"

    return True, "ok"


def _persist_attempt(
    state_path: Path,
    state: dict[str, Any],
    outcome: UpdateOutcome,
    *,
    last_success_head: Optional[str] = None,
    last_runner_restart_at: Optional[str] = None,
) -> dict[str, Any]:
    state["local_head"] = outcome.local_head
    state["remote_head"] = outcome.remote_head
    state["last_attempt_at"] = _utc_now_iso()
    state["last_result"] = outcome.result
    state["reason"] = outcome.reason
    if last_success_head is not None:
        state["last_success_head"] = last_success_head
    if last_runner_restart_at is not None:
        state["last_runner_restart_at"] = last_runner_restart_at
    save_updater_state(state_path, state)
    return state


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
        # Шаг 2: fetch origin only.
        code, out, err = git_runner(["fetch", "origin"], repo)
        if code != 0:
            outcome = UpdateOutcome(
                result="FAIL_CLOSED",
                reason="fetch_error",
                local_head=_read_head(repo, git_runner),
                remote_head=None,
            )
            _persist_attempt(state_path, state, outcome)
            LOGGER.warning("git fetch origin failed: %s", err or out)
            return outcome

        local_head = _read_head(repo, git_runner)
        remote_head = _read_remote_transition_head(
            repo, config.transition_branch, git_runner
        )

        # Шаг 3: NOOP если уже на remote head.
        if local_head and remote_head and local_head == remote_head:
            outcome = UpdateOutcome(
                result="NOOP",
                reason="already_current",
                local_head=local_head,
                remote_head=remote_head,
            )
            _persist_attempt(state_path, state, outcome)
            LOGGER.info("updater noop: already at remote head")
            return outcome

        # Шаг 4: maintenance exclusive.
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

        # Шаг 5: Coordinator process lock.
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

        # Шаг 6: preconditions (пока оба lock удерживаются).
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

        # Шаг 7: stop runner.
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
            _persist_attempt(state_path, state, outcome)
            LOGGER.warning(
                "systemctl stop failed: %s", stop_err or stop_out
            )
            return outcome
        runner_stopped = True

        # Шаг 8: единственная git-мутация — ff-only merge.
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
                _persist_attempt(state_path, state, outcome, last_runner_restart_at=restart_at)
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
            _persist_attempt(state_path, state, outcome)
            LOGGER.error("ff-only refused with uncertain state; runner left stopped")
            return outcome

        # Шаг 9: verify HEAD == remote и worktree clean.
        if not new_head or remote_head is None or new_head != remote_head:
            outcome = UpdateOutcome(
                result="HUMAN_REQUIRED",
                reason="post_merge_verification_failed",
                local_head=new_head,
                remote_head=remote_head,
                runner_stopped=runner_stopped,
                merge_attempted=True,
            )
            _persist_attempt(state_path, state, outcome)
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
            _persist_attempt(state_path, state, outcome)
            return outcome

        # Шаг 10: start runner exactly once on success.
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
            _persist_attempt(state_path, state, outcome)
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
