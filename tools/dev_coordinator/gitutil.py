"""Хелперы git / canonical repo id (read-only)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable, Optional, Sequence

GitRunner = Callable[[Sequence[str], Path], tuple[int, str, str]]


def default_git_runner(args: Sequence[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


# git@github.com:OWNER/REPO.git
_SSH_RE = re.compile(
    r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$"
)
# https://github.com/OWNER/REPO(.git)?
_HTTPS_RE = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)
# ssh://git@github.com/OWNER/REPO.git
_SSH_URL_RE = re.compile(
    r"^ssh://git@github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


def canonicalize_github_repo(url: str) -> Optional[str]:
    """Привести remote URL к виду OWNER/REPO или None если формат неизвестен."""
    raw = (url or "").strip()
    if not raw:
        return None
    for pattern in (_SSH_RE, _HTTPS_RE, _SSH_URL_RE):
        match = pattern.match(raw)
        if match:
            return f"{match.group('owner')}/{match.group('repo')}"
    return None


def read_origin_repo(
    worktree: Path,
    git_runner: GitRunner = default_git_runner,
) -> tuple[Optional[str], Optional[str]]:
    """Вернуть (canonical OWNER/REPO, raw origin url)."""
    code, out, _ = git_runner(["remote", "get-url", "origin"], worktree)
    if code != 0:
        return None, None
    raw = out.strip()
    return canonicalize_github_repo(raw), raw


def read_remote_branch_tip(
    worktree: Path,
    branch: str,
    git_runner: GitRunner = default_git_runner,
) -> Optional[str]:
    """Read-only: git ls-remote origin refs/heads/<branch>."""
    code, out, _ = git_runner(
        ["ls-remote", "origin", f"refs/heads/{branch}"],
        worktree,
    )
    if code != 0:
        return None
    line = out.strip().splitlines()[0] if out.strip() else ""
    if not line:
        return None
    sha = line.split()[0].strip()
    return sha or None
