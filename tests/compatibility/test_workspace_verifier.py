from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

from scripts.verify_consumer_contract_fixtures import verify_fixture
from tests.compatibility.fixture_contract import load_consumer_contracts


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "compatibility"
    / "consumer_contracts.v1.json"
)


def _run(*args: str, cwd: Path) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Compatibility Test",
        "GIT_AUTHOR_EMAIL": "compatibility@example.invalid",
        "GIT_COMMITTER_NAME": "Compatibility Test",
        "GIT_COMMITTER_EMAIL": "compatibility@example.invalid",
    }
    completed = subprocess.run(
        list(args), cwd=cwd, env=env, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def _workspace(tmp_path: Path) -> tuple[Path, str, Path]:
    workspace = tmp_path / "workspace"
    repository = workspace / "consumer"
    repository.mkdir(parents=True)
    _run("git", "init", "-q", cwd=repository)
    marker = tmp_path / "must-not-exist"
    source = (
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "PINNED = True\n"
    )
    (repository / "evidence.py").write_text(source, encoding="utf-8")
    _run("git", "add", "evidence.py", cwd=repository)
    _run("git", "commit", "-q", "-m", "fixture", cwd=repository)
    sha = _run("git", "rev-parse", "HEAD", cwd=repository)
    return workspace, sha, marker


def _fixture_for(repository: str, sha: str) -> dict:
    fixture = deepcopy(load_consumer_contracts(FIXTURE_PATH))
    for consumer in fixture["consumers"].values():
        consumer["provenance"].update(
            {"repository": repository, "sha": sha, "paths": ["evidence.py"]}
        )
        consumer["observed_evidence"]["facts"] = [
            {"kind": "contains", "path": "evidence.py", "match": "PINNED = True"},
            {"kind": "not_contains", "path": "evidence.py", "match": "DIRTY = True"},
        ]
    return fixture


def test_verifier_reads_exact_commit_and_never_executes_consumer_module(tmp_path: Path) -> None:
    workspace, sha, marker = _workspace(tmp_path)
    fixture = _fixture_for("consumer", sha)
    (workspace / "consumer" / "evidence.py").write_text(
        "DIRTY = True\n", encoding="utf-8"
    )

    assert verify_fixture(fixture, workspace) == []
    assert not marker.exists()


def test_verifier_accepts_safe_workspace_entry_that_is_a_repository_symlink(
    tmp_path: Path,
) -> None:
    workspace, sha, _ = _workspace(tmp_path)
    repository = workspace / "consumer"
    target = tmp_path / "mounted-consumer"
    repository.rename(target)
    repository.symlink_to(target, target_is_directory=True)

    assert verify_fixture(_fixture_for("consumer", sha), workspace) == []


def test_verifier_fails_closed_when_recorded_object_is_missing(tmp_path: Path) -> None:
    workspace, _, _ = _workspace(tmp_path)
    fixture = _fixture_for("consumer", "0" * 40)

    errors = verify_fixture(fixture, workspace)

    assert errors
    assert all("Git evidence unavailable" in error for error in errors)


def test_verifier_rejects_unrecognized_fact_kind(tmp_path: Path) -> None:
    workspace, sha, _ = _workspace(tmp_path)
    fixture = _fixture_for("consumer", sha)
    fixture["consumers"]["zoom"]["observed_evidence"]["facts"][0]["kind"] = "execute"

    errors = verify_fixture(fixture, workspace)

    assert any("unsupported fact kind" in error for error in errors)


def test_verifier_cli_returns_one_for_missing_ref(tmp_path: Path) -> None:
    workspace, _, _ = _workspace(tmp_path)
    fixture = _fixture_for("consumer", "0" * 40)
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "scripts/verify_consumer_contract_fixtures.py"),
            "--workspace-root",
            str(workspace),
            "--fixture",
            str(fixture_path),
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "Git evidence unavailable" in completed.stderr
