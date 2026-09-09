#!/usr/bin/env python3
"""Fail closed when a characterization branch changes production paths."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _safe_relative(path: str) -> bool:
    candidate = PurePosixPath(path)
    return bool(
        path
        and not candidate.is_absolute()
        and ".." not in candidate.parts
        and "\\" not in path
        and str(candidate) == path
    )


def _allowed(path: str) -> bool:
    if not _safe_relative(path):
        return False
    if path == ".github/workflows/ci.yml":
        return True
    if path.startswith(("tests/", "docs/")):
        return True
    candidate = PurePosixPath(path)
    return bool(
        len(candidate.parts) == 2
        and candidate.parts[0] == "scripts"
        and candidate.parts[1].startswith(("check_", "verify_"))
    )


def validate_paths(paths: Iterable[str]) -> list[str]:
    """Return disallowed paths in their original order."""
    return [path for path in paths if not _allowed(path)]


def changed_paths(repository: Path, base: str, head: str) -> list[str]:
    """Read the three-dot changed-path set for two exact commits."""
    if not _SHA_RE.fullmatch(base) or not _SHA_RE.fullmatch(head):
        raise ValueError("base and head must be lowercase 40-hex commit SHAs")
    completed = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if completed.returncode != 0:
        raise RuntimeError("unable to calculate characterization changed paths")
    return [line for line in completed.stdout.splitlines() if line]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args(argv)
    try:
        paths = changed_paths(args.repository, args.base, args.head)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    rejected = validate_paths(paths)
    if rejected:
        for path in rejected:
            print(path, file=sys.stderr)
        return 1
    print(f"verified {len(paths)} characterization-only changed paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
