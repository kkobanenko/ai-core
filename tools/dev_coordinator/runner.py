"""Persistent Coordinator runner: discovery, scheduling, delegation to run_once."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from tools.dev_coordinator.cli import DEFAULT_BRIDGE_REL, run_once
from tools.dev_coordinator.gitutil import GitRunner, default_git_runner
from tools.dev_coordinator.managed_worktrees import (
    prepare_bridge_worktree,
    prepare_executor_worktree,
    validate_declared_executor_path,
)
from tools.dev_coordinator.models import CoordState, FinalStatus
from tools.dev_coordinator.parse import parse_next_prompt
from tools.dev_coordinator.runner_config import (
    RunnerConfig,
    default_config_path,
    load_runner_config,
)
from tools.dev_coordinator.locks import MaintenanceGateLock
from tools.dev_coordinator.paths import default_state_dir

# Относительный путь prompt внутри bridge ref.
_BRIDGE_PROMPT_REL = DEFAULT_BRIDGE_REL

# Терминальные статусы runner (не перезапускать при том же SHA).
_TERMINAL_RUNNER_STATUSES = frozenset(
    {
        "SUCCESS",
        "FAIL_CLOSED",
        "HUMAN_REQUIRED",
        "EXECUTOR_FAILED",
        "PUBLICATION_FAILED",
        "REJECTED",
    }
)

LOGGER = logging.getLogger("dev_coordinator.runner")

CoordinatorInvoker = Callable[..., Any]


@dataclass(frozen=True)
class BridgeCandidate:
    """Обнаруженный bridge ref с prompt."""

    bridge_repo: str
    bridge_branch: str
    bridge_sha: str
    prompt_text: str


def runner_state_path(state_dir: Optional[Path] = None) -> Path:
    """Путь к JSON состоянию runner."""
    base = (state_dir or default_state_dir()).resolve()
    return base / "runner-state.json"


def package_key(bridge_repo: str, bridge_branch: str, bridge_sha: str) -> str:
    """Стабильный ключ пакета."""
    return f"{bridge_repo}|{bridge_branch}|{bridge_sha}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_runner_state(path: Path) -> dict[str, Any]:
    """Загрузить состояние runner (пустой dict если файла нет)."""
    if not path.is_file():
        return {"version": 1, "packages": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "packages": {}}
    if not isinstance(data, dict):
        return {"version": 1, "packages": {}}
    data.setdefault("version", 1)
    data.setdefault("packages", {})
    return data


def save_runner_state(path: Path, state: dict[str, Any]) -> None:
    """Атомарно сохранить состояние runner."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def is_terminal_package(state: dict[str, Any], key: str) -> bool:
    """Проверить, записан ли терминальный результат для ключа."""
    pkg = state.get("packages", {}).get(key, {})
    status = pkg.get("status")
    return status in _TERMINAL_RUNNER_STATUSES


def map_final_status(final: FinalStatus) -> str:
    """Сопоставить FinalStatus Coordinator → terminal runner status."""
    if final == FinalStatus.WORK_PACKAGE_SUCCESS:
        return "SUCCESS"
    if final in (FinalStatus.HUMAN_REQUIRED, FinalStatus.WAIT_OK):
        return "HUMAN_REQUIRED"
    if final in (
        FinalStatus.EXECUTOR_NONZERO,
        FinalStatus.EXECUTOR_PROCESS_EXITED_ZERO,
    ):
        return "EXECUTOR_FAILED"
    if final in (
        FinalStatus.PUBLICATION_FAILED,
        FinalStatus.PUBLICATION_UNVERIFIED,
    ):
        return "PUBLICATION_FAILED"
    if final == FinalStatus.FAIL_CLOSED:
        return "FAIL_CLOSED"
    if final in (
        FinalStatus.POSTCONDITION_FAILED,
        FinalStatus.VALIDATION_FAILED,
        FinalStatus.SHADOW_OK,
    ):
        return "FAIL_CLOSED"
    return "FAIL_CLOSED"


def discover_bridge_refs(
    repo_clone: Path,
    bridge_prefix: str,
    git_runner: GitRunner,
) -> tuple[list[tuple[str, str]], Optional[str]]:
    """Перечислить (branch, sha) только под coord/bridge/*."""
    prefix = bridge_prefix.rstrip("/")
    ref_pattern = f"refs/remotes/origin/{prefix}/"
    code, out, err = git_runner(
        [
            "for-each-ref",
            "--format=%(objectname) %(refname:strip=3)",
            ref_pattern,
        ],
        repo_clone,
    )
    if code != 0:
        return [], f"for-each-ref failed: {err or out}".strip()

    results: list[tuple[str, str]] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        sha, branch = parts[0].strip(), parts[1].strip()
        if not branch.startswith("coord/bridge/"):
            continue
        if not sha:
            continue
        results.append((branch, sha))
    return results, None


def read_remote_prompt(
    repo_clone: Path,
    bridge_sha: str,
    git_runner: GitRunner,
) -> tuple[Optional[str], Optional[str]]:
    """Прочитать next-prompt.md с точного remote SHA."""
    code, out, err = git_runner(
        ["show", f"{bridge_sha}:{_BRIDGE_PROMPT_REL}"],
        repo_clone,
    )
    if code != 0:
        return None, f"unable to read prompt at {_BRIDGE_PROMPT_REL}: {err or out}".strip()
    return out, None


def fetch_origin(
    repo_clone: Path,
    git_runner: GitRunner,
) -> Optional[str]:
    """git fetch origin --prune; вернуть ошибку или None."""
    code, out, err = git_runner(["fetch", "origin", "--prune"], repo_clone)
    if code != 0:
        return f"git fetch failed for {repo_clone}: {err or out}".strip()
    return None


def record_package_result(
    state: dict[str, Any],
    *,
    key: str,
    bridge_repo: str,
    bridge_branch: str,
    bridge_sha: str,
    prompt_id: Optional[str],
    target_repo: Optional[str],
    target_branch: Optional[str],
    status: str,
    reason: str,
    coordinator_final_status: Optional[str] = None,
    publication_sha: Optional[str] = None,
    log_path: Optional[str] = None,
) -> None:
    """Записать терминальный результат пакета."""
    packages = state.setdefault("packages", {})
    packages[key] = {
        "bridge_repo": bridge_repo,
        "bridge_branch": bridge_branch,
        "bridge_sha": bridge_sha,
        "prompt_id": prompt_id,
        "target_repo": target_repo,
        "target_branch": target_branch,
        "status": status,
        "reason": reason,
        "coordinator_final_status": coordinator_final_status,
        "publication_sha": publication_sha,
        "log_path": log_path,
        "updated_at": _utc_now_iso(),
    }
    state["last_scan_at"] = _utc_now_iso()


def validate_candidate(
    prompt_text: str,
    config: RunnerConfig,
    bridge_repo: str,
) -> tuple[Optional[Any], Optional[str]]:
    """Проверить prompt и метаданные до worktree prep."""
    prompt = parse_next_prompt(prompt_text)

    if prompt.parse_error:
        return None, f"parse error: {prompt.parse_error}"

    if prompt.state != CoordState.EXECUTOR_READY:
        return None, f"ignored non-ready state: {prompt.state}"

    if not prompt.target_repo:
        return None, "missing target_repo"

    if prompt.target_repo not in config.repositories:
        return (
            None,
            f"target_repo not in allowlist: {prompt.target_repo}",
        )

    if not prompt.target_branch:
        return None, "missing target_branch"

    if prompt.target_branch in ("main", "master"):
        return None, f"forbidden target branch: {prompt.target_branch}"

    if not prompt.target_worktree:
        return None, "missing target_worktree"

    ok, reason, _ = validate_declared_executor_path(
        prompt.target_worktree,
        config.managed_worktree_root,
        prompt.target_repo,
        prompt.target_branch,
    )
    if not ok:
        return None, reason

    return prompt, None


def process_candidate(
    candidate: BridgeCandidate,
    config: RunnerConfig,
    *,
    git_runner: GitRunner,
    coordinator_invoker: CoordinatorInvoker,
    state_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Обработать один bridge candidate (worktrees + Coordinator)."""
    prompt_text = candidate.prompt_text
    prompt, reject_reason = validate_candidate(
        prompt_text, config, candidate.bridge_repo
    )
    key = package_key(
        candidate.bridge_repo, candidate.bridge_branch, candidate.bridge_sha
    )

    if prompt is None:
        return {
            "key": key,
            "status": "REJECTED",
            "reason": reject_reason or "rejected",
            "launched": False,
        }

    target_clone = config.repo_path(prompt.target_repo)
    if target_clone is None:
        return {
            "key": key,
            "status": "REJECTED",
            "reason": f"no clone for {prompt.target_repo}",
            "launched": False,
        }

    bridge_clone = config.repositories[candidate.bridge_repo]

    bridge_prep = prepare_bridge_worktree(
        repo_clone=bridge_clone,
        canonical_repo=candidate.bridge_repo,
        bridge_branch=candidate.bridge_branch,
        bridge_sha=candidate.bridge_sha,
        managed_root=config.managed_worktree_root,
        git_runner=git_runner,
    )
    if not bridge_prep.ok or bridge_prep.path is None:
        return {
            "key": key,
            "status": "FAIL_CLOSED",
            "reason": f"bridge worktree: {bridge_prep.reason}",
            "launched": False,
            "prompt_id": prompt.prompt_id,
            "target_repo": prompt.target_repo,
            "target_branch": prompt.target_branch,
        }

    executor_prep = prepare_executor_worktree(
        repo_clone=target_clone,
        canonical_repo=prompt.target_repo,
        target_branch=prompt.target_branch,
        base_sha=prompt.base_sha or "",
        declared_worktree=Path(prompt.target_worktree),
        managed_root=config.managed_worktree_root,
        git_runner=git_runner,
    )
    if not executor_prep.ok or executor_prep.path is None:
        return {
            "key": key,
            "status": "FAIL_CLOSED",
            "reason": f"executor worktree: {executor_prep.reason}",
            "launched": False,
            "prompt_id": prompt.prompt_id,
            "target_repo": prompt.target_repo,
            "target_branch": prompt.target_branch,
        }

    bridge_prompt_path = bridge_prep.path / _BRIDGE_PROMPT_REL
    # Записать актуальный prompt в worktree для Coordinator.
    bridge_prompt_path.parent.mkdir(parents=True, exist_ok=True)
    bridge_prompt_path.write_text(prompt_text, encoding="utf-8")

    result = coordinator_invoker(
        mode="launch",
        repo_root=target_clone,
        executor_worktree=executor_prep.path,
        bridge_prompt_path=bridge_prompt_path,
        bridge_worktree=bridge_prep.path,
        agent_bin=str(config.agent_bin),
        state_dir=state_dir,
        git_runner=git_runner,
    )

    runner_status = map_final_status(result.final_status)
    return {
        "key": key,
        "status": runner_status,
        "reason": result.decision.reason,
        "launched": result.executor_launched,
        "prompt_id": prompt.prompt_id,
        "target_repo": prompt.target_repo,
        "target_branch": prompt.target_branch,
        "coordinator_final_status": result.final_status.value,
        "publication_sha": result.remote_head,
        "log_path": result.executor_log_path,
    }


def scan_repositories(
    config: RunnerConfig,
    *,
    git_runner: GitRunner = default_git_runner,
    coordinator_invoker: CoordinatorInvoker = run_once,
    state_dir: Optional[Path] = None,
    state_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Один цикл опроса: fetch, discover, serial process."""
    state_file = state_path or runner_state_path(state_dir)
    state = load_runner_state(state_file)
    summary: dict[str, Any] = {
        "scanned_repos": [],
        "candidates_found": 0,
        "processed": [],
        "skipped_terminal": 0,
        "errors": [],
    }

    candidates: list[BridgeCandidate] = []

    for bridge_repo, clone_path in sorted(config.repositories.items()):
        summary["scanned_repos"].append(bridge_repo)
        fetch_err = fetch_origin(clone_path, git_runner)
        if fetch_err:
            summary["errors"].append(fetch_err)
            LOGGER.warning("%s", fetch_err)
            continue

        refs, ref_err = discover_bridge_refs(
            clone_path, config.bridge_prefix, git_runner
        )
        if ref_err:
            summary["errors"].append(ref_err)
            LOGGER.warning("%s", ref_err)
            continue

        for branch, sha in refs:
            key = package_key(bridge_repo, branch, sha)
            if is_terminal_package(state, key):
                summary["skipped_terminal"] += 1
                continue

            prompt_text, read_err = read_remote_prompt(clone_path, sha, git_runner)
            if read_err or prompt_text is None:
                summary["errors"].append(
                    f"{bridge_repo}/{branch}@{sha}: {read_err}"
                )
                continue

            candidates.append(
                BridgeCandidate(
                    bridge_repo=bridge_repo,
                    bridge_branch=branch,
                    bridge_sha=sha,
                    prompt_text=prompt_text,
                )
            )

    summary["candidates_found"] = len(candidates)

    # Сериальная обработка (один пакет за раз).
    for candidate in candidates:
        outcome = process_candidate(
            candidate,
            config,
            git_runner=git_runner,
            coordinator_invoker=coordinator_invoker,
            state_dir=state_dir,
        )
        summary["processed"].append(outcome)

        record_package_result(
            state,
            key=outcome["key"],
            bridge_repo=candidate.bridge_repo,
            bridge_branch=candidate.bridge_branch,
            bridge_sha=candidate.bridge_sha,
            prompt_id=outcome.get("prompt_id"),
            target_repo=outcome.get("target_repo"),
            target_branch=outcome.get("target_branch"),
            status=outcome["status"],
            reason=outcome.get("reason", ""),
            coordinator_final_status=outcome.get("coordinator_final_status"),
            publication_sha=outcome.get("publication_sha"),
            log_path=outcome.get("log_path"),
        )
        save_runner_state(state_file, state)

    if summary["errors"]:
        state["last_error"] = "; ".join(summary["errors"][-3:])
    else:
        state["last_error"] = None
    state["last_scan_at"] = _utc_now_iso()
    save_runner_state(state_file, state)

    return summary


def scan_with_maintenance_gate(
    config: RunnerConfig,
    *,
    git_runner: GitRunner = default_git_runner,
    coordinator_invoker: CoordinatorInvoker = run_once,
    state_dir: Optional[Path] = None,
    state_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Один цикл опроса с maintenance gate shared (runner cooperation)."""
    effective_state_dir = (state_dir or default_state_dir()).resolve()
    gate = MaintenanceGateLock(effective_state_dir, mode="shared")
    if not gate.acquire():
        LOGGER.info(
            "maintenance gate exclusive held by updater; skipping scan cycle"
        )
        return {
            "skipped": True,
            "skip_reason": "maintenance_held",
            "scanned_repos": [],
            "candidates_found": 0,
            "processed": [],
            "skipped_terminal": 0,
            "errors": [],
        }
    try:
        return scan_repositories(
            config,
            git_runner=git_runner,
            coordinator_invoker=coordinator_invoker,
            state_dir=state_dir,
            state_path=state_path,
        )
    finally:
        gate.release()


def build_status_report(
    config: RunnerConfig,
    state_path: Optional[Path] = None,
    state_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Read-only статус runner."""
    path = state_path or runner_state_path(state_dir)
    state = load_runner_state(path)
    packages = state.get("packages", {})
    return {
        "config_path": str(default_config_path()),
        "state_path": str(path),
        "poll_interval_seconds": config.poll_interval_seconds,
        "managed_worktree_root": str(config.managed_worktree_root),
        "repositories": {
            name: str(path) for name, path in config.repositories.items()
        },
        "last_scan_at": state.get("last_scan_at"),
        "last_error": state.get("last_error"),
        "package_count": len(packages),
        "packages": packages,
    }


def run_loop(
    config: RunnerConfig,
    *,
    once: bool = False,
    git_runner: GitRunner = default_git_runner,
    coordinator_invoker: CoordinatorInvoker = run_once,
    state_dir: Optional[Path] = None,
    stop_event: Optional[Callable[[], bool]] = None,
) -> None:
    """Persistent polling loop или один проход (--once)."""
    should_stop = stop_event or (lambda: False)

    while True:
        try:
            summary = scan_with_maintenance_gate(
                config,
                git_runner=git_runner,
                coordinator_invoker=coordinator_invoker,
                state_dir=state_dir,
            )
            LOGGER.info(
                "scan complete: candidates=%s processed=%s skipped_terminal=%s errors=%s",
                summary["candidates_found"],
                len(summary["processed"]),
                summary["skipped_terminal"],
                len(summary["errors"]),
            )
        except Exception as exc:  # noqa: BLE001 — сервис должен продолжить
            LOGGER.exception("scan failed: %s", exc)

        if once or should_stop():
            break
        time.sleep(config.poll_interval_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dev_coordinator.runner",
        description="Persistent Coordinator runner (discovery + scheduling).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to runner.json (default: XDG config path)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single scan cycle and exit",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print read-only status and exit",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output for --status or --once summary",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="Override Coordinator state directory",
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
        config = load_runner_config(config_path)
    except (OSError, ValueError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    state_dir = args.state_dir.resolve() if args.state_dir else None

    if args.status:
        report = build_status_report(config, state_dir=state_dir)
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(f"state_path: {report['state_path']}")
            print(f"last_scan_at: {report['last_scan_at']}")
            print(f"last_error: {report['last_error']}")
            print(f"packages: {report['package_count']}")
            for key, pkg in report["packages"].items():
                print(
                    f"  {key}: status={pkg.get('status')} "
                    f"prompt_id={pkg.get('prompt_id')}"
                )
        return 0

    if args.once:
        summary = scan_with_maintenance_gate(config, state_dir=state_dir)
        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        elif summary.get("skipped"):
            print(
                f"SCAN skipped reason={summary.get('skip_reason', 'maintenance_held')}"
            )
        else:
            print(
                f"SCAN candidates={summary['candidates_found']} "
                f"processed={len(summary['processed'])} "
                f"skipped_terminal={summary['skipped_terminal']} "
                f"errors={len(summary['errors'])}"
            )
        return 0

    run_loop(config, once=False, state_dir=state_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
