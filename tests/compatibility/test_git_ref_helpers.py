from __future__ import annotations

import pytest

from tests.compatibility.git_ref import (
    RefEvidenceError,
    list_paths,
    read_blob,
    resolve_tag,
)


IMMUTABLE_TAGS = {
    "v0.1.0": "f7886b51ea4b87b734181a91de06644faaf0ef7e",
    "v0.2.0": "e479d0af314714a96c959a2ea677abdcb0942af7",
    "v0.2.1": "f743057a02a8b69bf943b615510d4745d737e16a",
    "v0.2.2": "679b88fa7cd6e9f64b543c405a90b2ef0dcdc575",
}


@pytest.mark.parametrize(("tag", "sha"), IMMUTABLE_TAGS.items())
def test_immutable_tag_peels_to_recorded_commit(tag: str, sha: str) -> None:
    assert resolve_tag(tag) == sha


def test_read_blob_requires_exact_sha_and_returns_tag_content() -> None:
    source = read_blob(IMMUTABLE_TAGS["v0.2.0"], "pyproject.toml")
    assert 'version = "0.2.0"' in source


@pytest.mark.parametrize(
    "path",
    ["/etc/passwd", "../pyproject.toml", "src/../pyproject.toml", ""],
)
def test_read_blob_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValueError, match="safe repository-relative path"):
        read_blob(IMMUTABLE_TAGS["v0.2.0"], path)


def test_read_blob_rejects_mutable_or_malformed_ref() -> None:
    with pytest.raises(ValueError, match="40-hex commit SHA"):
        read_blob("v0.2.0", "pyproject.toml")


def test_missing_object_fails_without_fetching() -> None:
    with pytest.raises(RefEvidenceError, match="Git evidence unavailable"):
        read_blob("0" * 40, "pyproject.toml")


def test_list_paths_returns_exact_tree_under_safe_prefix() -> None:
    assert list_paths(IMMUTABLE_TAGS["v0.1.0"], "src/ai_core") == (
        "src/ai_core/__init__.py",
        "src/ai_core/attributes.py",
        "src/ai_core/config.py",
        "src/ai_core/io_policy.py",
        "src/ai_core/tracing.py",
    )
