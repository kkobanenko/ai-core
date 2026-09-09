#!/usr/bin/env python3
"""Verify consumer fixture facts against pinned local Git objects only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tests.compatibility.fixture_contract import (  # noqa: E402
    load_consumer_contracts,
    validate_consumer_contracts,
)


DEFAULT_FIXTURE = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "compatibility"
    / "consumer_contracts.v1.json"
)
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SUPPORTED_FACTS = {"contains", "not_contains", "json_or_yaml_literal"}


def _safe_relative(value: str) -> bool:
    candidate = PurePosixPath(value)
    return bool(
        value
        and not candidate.is_absolute()
        and ".." not in candidate.parts
        and "\\" not in value
        and str(candidate) == value
    )


def _read_blob(repository: Path, sha: str, path: str) -> str:
    if not _SHA_RE.fullmatch(sha) or not _safe_relative(path):
        raise RuntimeError("Git evidence unavailable for recorded object")
    completed = subprocess.run(
        ["git", "-C", str(repository), "show", f"{sha}:{path}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if completed.returncode != 0:
        raise RuntimeError("Git evidence unavailable for recorded object")
    return completed.stdout


def _lookup_json_or_yaml_literal(source: str, key: str) -> object:
    try:
        current: object = json.loads(source)
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                raise KeyError(key)
            current = current[part]
        return current
    except json.JSONDecodeError:
        leaf = key.rsplit(".", 1)[-1]
        match = re.search(rf"(?m)^\s*{re.escape(leaf)}\s*:\s*(.*?)\s*$", source)
        if match is None:
            raise KeyError(key)
        value = match.group(1).split(" #", 1)[0].strip().strip("'\"")
        if value.lower() in {"true", "false"}:
            return value.lower() == "true"
        if re.fullmatch(r"-?[0-9]+", value):
            return int(value)
        return value


def verify_fixture(data: object, workspace_root: Path) -> list[str]:
    """Return content-free diagnostics for fixture or pinned-evidence drift."""
    validation_errors = validate_consumer_contracts(data)
    if validation_errors:
        return validation_errors
    assert isinstance(data, dict)
    consumers = data["consumers"]
    workspace = workspace_root
    errors: list[str] = []
    cache: dict[tuple[Path, str, str], str] = {}

    for name, consumer in consumers.items():
        provenance = consumer["provenance"]
        repository_name = provenance["repository"]
        if not isinstance(repository_name, str) or not _safe_relative(repository_name):
            errors.append(f"$.consumers.{name}.provenance.repository: unsafe repository path")
            continue
        repository = workspace / repository_name
        sha = provenance["sha"]
        for index, fact in enumerate(consumer["observed_evidence"].get("facts", [])):
            base = f"$.consumers.{name}.observed_evidence.facts[{index}]"
            if not isinstance(fact, dict) or fact.get("kind") not in _SUPPORTED_FACTS:
                errors.append(f"{base}: unsupported fact kind")
                continue
            path = fact.get("path")
            if not isinstance(path, str):
                errors.append(f"{base}.path: invalid evidence path")
                continue
            cache_key = (repository, sha, path)
            try:
                source = cache.setdefault(cache_key, _read_blob(repository, sha, path))
            except (OSError, subprocess.SubprocessError, RuntimeError):
                errors.append(f"{base}: Git evidence unavailable for recorded object")
                continue
            kind = fact["kind"]
            if kind in {"contains", "not_contains"}:
                expected = fact.get("match")
                if not isinstance(expected, str):
                    errors.append(f"{base}.match: expected string")
                elif (expected in source) != (kind == "contains"):
                    errors.append(f"{base}: pinned evidence drift")
            else:
                key = fact.get("key")
                if not isinstance(key, str) or "expected" not in fact:
                    errors.append(f"{base}: literal fact requires key and expected")
                    continue
                try:
                    actual = _lookup_json_or_yaml_literal(source, key)
                except (KeyError, TypeError):
                    errors.append(f"{base}: pinned evidence drift")
                else:
                    if actual != fact["expected"]:
                        errors.append(f"{base}: pinned evidence drift")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    args = parser.parse_args(argv)
    try:
        data = load_consumer_contracts(args.fixture)
        errors = verify_fixture(data, args.workspace_root)
    except (OSError, ValueError, json.JSONDecodeError):
        print("consumer fixture could not be loaded", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"verified {len(data['consumers'])} pinned consumer contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
