from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from tests.compatibility.fixture_contract import (
    load_consumer_contracts,
    validate_consumer_contracts,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "compatibility"
    / "consumer_contracts.v1.json"
)
EXPECTED_CONSUMERS = {
    "prozakupki",
    "kmo",
    "zoom",
    "clin_rec",
    "landing_sell",
    "agent_lab",
    "alpha_university",
    "transcription_service",
    "image_description_service",
}
REQUIRED_SECTIONS = {
    "observed_evidence",
    "consumer_requirement",
    "accepted_platform_contract",
    "proposed_behavior",
    "governance_pending",
}


def test_checked_in_consumer_fixture_has_strict_top_level_shape() -> None:
    data = load_consumer_contracts(FIXTURE_PATH)

    assert validate_consumer_contracts(data) == []
    assert data["schema_version"] == 1
    assert set(data["consumers"]) == EXPECTED_CONSUMERS
    assert data["accepted_provider_ids"] == [
        "vm100_local_ollama",
        "gpu_ollama",
        "ollama_cloud",
        "mistral_external",
    ]
    assert all(
        REQUIRED_SECTIONS.issubset(consumer)
        for consumer in data["consumers"].values()
    )


def test_validator_rejects_provider_identity_expansion() -> None:
    data = load_consumer_contracts(FIXTURE_PATH)
    changed = deepcopy(data)
    changed["accepted_provider_ids"].append("unreviewed_provider")

    errors = validate_consumer_contracts(changed)

    assert any("$.accepted_provider_ids" in error for error in errors)


def test_validator_rejects_content_or_credential_shaped_fields_without_echoing_value() -> None:
    data = load_consumer_contracts(FIXTURE_PATH)
    changed = deepcopy(data)
    sensitive_value = "sk-example-value-that-must-not-appear"
    changed["consumers"]["zoom"]["observed_evidence"]["prompt"] = sensitive_value

    errors = validate_consumer_contracts(changed)

    assert any("prompt" in error for error in errors)
    assert all(sensitive_value not in error for error in errors)


def test_validator_rejects_urls_with_userinfo_or_query_secrets() -> None:
    data = load_consumer_contracts(FIXTURE_PATH)
    changed = deepcopy(data)
    changed["consumers"]["zoom"]["current_path"] = (
        "https://user:password@example.invalid/path?token=hidden"
    )

    errors = validate_consumer_contracts(changed)

    assert any("$.consumers.zoom.current_path" in error for error in errors)
    assert all("password" not in error and "hidden" not in error for error in errors)


def test_validator_requires_exact_provenance_and_retry_shapes() -> None:
    data = load_consumer_contracts(FIXTURE_PATH)
    changed = deepcopy(data)
    del changed["consumers"]["kmo"]["provenance"]["sha"]
    del changed["consumers"]["kmo"]["retry"]["durable_job"]

    errors = validate_consumer_contracts(changed)

    assert any("$.consumers.kmo.provenance.sha" in error for error in errors)
    assert any("$.consumers.kmo.retry.durable_job" in error for error in errors)
