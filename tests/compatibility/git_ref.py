"""Read-only access to pinned Git evidence; never fetches or accepts branches."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import re
import subprocess


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_TAG_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class RefEvidenceError(RuntimeError):
    """Pinned Git evidence is unavailable in the local clone."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if completed.returncode != 0:
        raise RefEvidenceError("Git evidence unavailable for the requested object")
    return completed.stdout


def resolve_tag(tag: str) -> str:
    """Peel a semantic-version tag to a commit without any network access."""
    if not _TAG_RE.fullmatch(tag):
        raise ValueError("tag must be an exact semantic-version tag")
    sha = _git("rev-parse", "--verify", f"{tag}^{{commit}}").strip()
    if not _SHA_RE.fullmatch(sha):
        raise RefEvidenceError("Git evidence unavailable for the requested tag")
    return sha


def _validate_sha_and_path(sha: str, path: str) -> None:
    if not _SHA_RE.fullmatch(sha):
        raise ValueError("ref must be a lowercase 40-hex commit SHA")
    candidate = PurePosixPath(path)
    if (
        not path
        or candidate.is_absolute()
        or ".." in candidate.parts
        or "\\" in path
        or str(candidate) != path
    ):
        raise ValueError("path must be a safe repository-relative path")


def read_blob(sha: str, path: str) -> str:
    """Return one UTF-8 Git blob from an exact commit SHA and safe path."""
    _validate_sha_and_path(sha, path)
    return _git("show", f"{sha}:{path}")


def list_paths(sha: str, prefix: str) -> tuple[str, ...]:
    """List tracked paths below a safe prefix at an exact commit."""
    _validate_sha_and_path(sha, prefix)
    output = _git("ls-tree", "-r", "--name-only", sha, "--", prefix)
    return tuple(line for line in output.splitlines() if line)
