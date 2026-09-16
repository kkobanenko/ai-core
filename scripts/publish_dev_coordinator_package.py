#!/usr/bin/env python3
"""CLI Architect-side публикации bounded work package."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Корень репозитория Coordinator — источник tools.* (cwd может быть любым).
_REPO_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT_STR = str(_REPO_ROOT)
if _REPO_ROOT_STR not in sys.path:
    sys.path.insert(0, _REPO_ROOT_STR)

from tools.dev_coordinator.package_publisher import (  # noqa: E402
    WorkPackageSpec,
    format_result_json,
    publish_work_package,
    resolve_bridge_branch,
)
from tools.dev_coordinator.runner_config import default_config_path  # noqa: E402


def _split_paths(value: str) -> tuple[str, ...]:
    """Разобрать comma-separated пути из CLI."""
    parts: list[str] = []
    for item in value.split(","):
        item = item.strip()
        if item:
            parts.append(item)
    return tuple(parts)


def build_parser() -> argparse.ArgumentParser:
    """Построить argparse для publisher CLI."""
    parser = argparse.ArgumentParser(
        description="Publish Architect work package (target + coord/bridge branch).",
    )
    parser.add_argument(
        "--runner-config",
        type=Path,
        default=None,
        help="Path to runner.json (default: ~/.config/ai-core-dev-coordinator/runner.json)",
    )
    parser.add_argument("--bridge-repo", required=True, help="Canonical OWNER/REPO")
    parser.add_argument("--target-repo", required=True, help="Canonical OWNER/REPO")
    parser.add_argument("--base-sha", required=True, help="Exact target base commit SHA")
    parser.add_argument("--target-branch", required=True, help="Target feature branch")
    parser.add_argument(
        "--bridge-branch",
        default=None,
        help=f"Bridge branch (must start with coord/bridge/)",
    )
    parser.add_argument(
        "--package-id",
        default=None,
        help="Deterministic package id → coord/bridge/<package-id>",
    )
    parser.add_argument("--prompt-id", required=True, help="Unique prompt identifier")
    parser.add_argument(
        "--allowed-paths",
        required=True,
        help="Comma-separated allowed_paths",
    )
    parser.add_argument(
        "--required-paths",
        required=True,
        help="Comma-separated required_paths",
    )
    parser.add_argument(
        "--transient-paths",
        default="",
        help="Comma-separated transient_paths (optional)",
    )
    parser.add_argument("--commit-message", required=True)
    parser.add_argument(
        "--hosted-ci",
        default="forbidden",
        choices=["forbidden", "read_only", "informational"],
    )
    parser.add_argument(
        "--publication-commit",
        default=True,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--publication-push",
        default=True,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument("--max-executor-runs", type=int, default=1)
    parser.add_argument(
        "--instruction-file",
        type=Path,
        required=True,
        help="Path to instruction body (markdown after front matter)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and render only; no git/filesystem mutation",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON result only",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        bridge_branch = resolve_bridge_branch(
            bridge_branch=args.bridge_branch,
            package_id=args.package_id,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    config_path = args.runner_config or default_config_path()
    try:
        body = args.instruction_file.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: unable to read instruction file: {exc}", file=sys.stderr)
        return 2

    spec = WorkPackageSpec(
        runner_config_path=config_path.resolve(),
        bridge_repo=args.bridge_repo.strip(),
        target_repo=args.target_repo.strip(),
        base_sha=args.base_sha.strip(),
        target_branch=args.target_branch.strip(),
        bridge_branch=bridge_branch,
        prompt_id=args.prompt_id.strip(),
        allowed_paths=_split_paths(args.allowed_paths),
        required_paths=_split_paths(args.required_paths),
        transient_paths=_split_paths(args.transient_paths),
        commit_message=args.commit_message,
        hosted_ci=args.hosted_ci,
        publication_commit=bool(args.publication_commit),
        publication_push=bool(args.publication_push),
        max_executor_runs=args.max_executor_runs,
        instruction_body=body,
        dry_run=bool(args.dry_run),
    )

    outcome = publish_work_package(spec)

    if args.json:
        print(format_result_json(outcome))
    else:
        print(outcome.format_human())
        if outcome.next_prompt_text and outcome.dry_run:
            print("\n--- next-prompt preview ---\n")
            print(outcome.next_prompt_text.rstrip())

    return 0 if outcome.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
