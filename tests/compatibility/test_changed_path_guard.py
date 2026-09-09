from __future__ import annotations

import os
from pathlib import Path
import subprocess

from scripts.check_characterization_changed_paths import (
    changed_paths,
    main,
    validate_paths,
)


def _git(repository: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Compatibility Test",
        "GIT_AUTHOR_EMAIL": "compatibility@example.invalid",
        "GIT_COMMITTER_NAME": "Compatibility Test",
        "GIT_COMMITTER_EMAIL": "compatibility@example.invalid",
    }
    completed = subprocess.run(
        ["git", *args],
        cwd=repository,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _commit(repository: Path, path: str, content: str) -> str:
    target = repository / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repository, "add", path)
    _git(repository, "commit", "-q", "-m", path)
    return _git(repository, "rev-parse", "HEAD")


def test_validate_paths_accepts_only_characterization_locations() -> None:
    assert validate_paths(
        [
            ".github/workflows/ci.yml",
            "tests/compatibility/test_guard.py",
            "tests/fixtures/compatibility/facts.json",
            "scripts/check_characterization_changed_paths.py",
            "scripts/verify_consumer_contract_fixtures.py",
            "docs/reports/report.md",
        ]
    ) == []


def test_validate_paths_rejects_runtime_manifests_config_and_unsafe_paths() -> None:
    paths = [
        "src/ai_core/runtime.py",
        "pyproject.toml",
        "config/providers.yaml",
        "/absolute/test.py",
        "docs/../src/ai_core/client.py",
        "README.md",
        "scripts/migrate_consumers.py",
    ]

    assert validate_paths(paths) == paths


def test_git_diff_and_cli_accept_documentation_only_commit(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "-q")
    base = _commit(repository, "docs/base.md", "base\n")
    head = _commit(repository, "tests/compatibility/test_fact.py", "FACT = True\n")

    assert changed_paths(repository, base, head) == [
        "tests/compatibility/test_fact.py"
    ]
    assert main(
        ["--repository", str(repository), "--base", base, "--head", head]
    ) == 0


def test_cli_rejects_disallowed_change_and_non_sha_ref(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "-q")
    base = _commit(repository, "docs/base.md", "base\n")
    head = _commit(repository, "src/ai_core/runtime.py", "RUNTIME = True\n")

    assert main(
        ["--repository", str(repository), "--base", base, "--head", head]
    ) == 1
    assert main(
        ["--repository", str(repository), "--base", base, "--head", "HEAD"]
    ) == 2
