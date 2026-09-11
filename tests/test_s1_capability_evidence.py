from dataclasses import FrozenInstanceError, fields

import pytest

from ai_core.capabilities import (
    CapabilityEvidence,
    CapabilityEvidenceLevel,
    ProviderCapability,
    has_runtime_observation,
)
from ai_core.provider_catalog import (
    NetworkBoundary,
    UnknownProviderIdentityError,
)


def test_capability_and_evidence_vocabularies_are_exact() -> None:
    assert [capability.value for capability in ProviderCapability] == [
        "text",
        "structured_json",
        "vision_image",
        "ocr_pdf",
    ]
    assert [level.value for level in CapabilityEvidenceLevel] == [
        "CONFIGURED",
        "UNIT_TESTED",
        "INTEGRATION_TESTED",
        "RUNTIME_OBSERVED",
        "FAILED_INCONCLUSIVE",
    ]
    assert "STT_SEGMENTS" not in ProviderCapability.__members__


def test_evidence_subject_is_immutable_and_model_scoped() -> None:
    evidence = CapabilityEvidence(
        provider_id="mistral_external",
        model="mistral-ocr-latest",
        capability=ProviderCapability.OCR_PDF,
        network_boundary=NetworkBoundary.EXTERNAL,
        level=CapabilityEvidenceLevel.RUNTIME_OBSERVED,
    )

    assert [field.name for field in fields(CapabilityEvidence)] == [
        "provider_id",
        "model",
        "capability",
        "network_boundary",
        "level",
    ]
    with pytest.raises(FrozenInstanceError):
        evidence.level = CapabilityEvidenceLevel.CONFIGURED  # type: ignore[misc]


def test_unknown_provider_identity_fails_closed_during_evidence_creation() -> None:
    with pytest.raises(
        UnknownProviderIdentityError,
        match="Unknown provider identity: openai_external",
    ):
        CapabilityEvidence(
            provider_id="openai_external",
            model="unknown",
            capability=ProviderCapability.TEXT,
            network_boundary=NetworkBoundary.EXTERNAL,
            level=CapabilityEvidenceLevel.CONFIGURED,
        )


def test_evidence_boundary_must_match_governed_provider_boundary() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Boundary mismatch for gpu_ollama: governed=unknown_boundary "
            "evidence=local_same_host"
        ),
    ):
        CapabilityEvidence(
            provider_id="gpu_ollama",
            model="qwen3-vl:4b",
            capability=ProviderCapability.VISION_IMAGE,
            network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
            level=CapabilityEvidenceLevel.FAILED_INCONCLUSIVE,
        )


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (CapabilityEvidenceLevel.CONFIGURED, False),
        (CapabilityEvidenceLevel.UNIT_TESTED, False),
        (CapabilityEvidenceLevel.INTEGRATION_TESTED, False),
        (CapabilityEvidenceLevel.RUNTIME_OBSERVED, True),
        (CapabilityEvidenceLevel.FAILED_INCONCLUSIVE, False),
    ],
)
def test_only_runtime_observed_counts_as_runtime_observation(
    level: CapabilityEvidenceLevel,
    expected: bool,
) -> None:
    evidence = CapabilityEvidence(
        provider_id="gpu_ollama",
        model="qwen3-vl:4b",
        capability=ProviderCapability.VISION_IMAGE,
        network_boundary=NetworkBoundary.UNKNOWN_BOUNDARY,
        level=level,
    )

    assert has_runtime_observation(evidence) is expected


def test_runtime_observation_does_not_expose_routing_eligibility() -> None:
    evidence = CapabilityEvidence(
        provider_id="vm100_local_ollama",
        model="qwen3.5:9b",
        capability=ProviderCapability.TEXT,
        network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
        level=CapabilityEvidenceLevel.RUNTIME_OBSERVED,
    )

    assert has_runtime_observation(evidence) is True
    assert not hasattr(evidence, "routing_eligible")
    assert not hasattr(evidence, "production_eligible")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"provider_id": None}, "provider_id must be a non-empty string"),
        ({"model": ""}, "model must be a non-empty string"),
        ({"capability": "STT_SEGMENTS"}, "capability must be ProviderCapability"),
        ({"network_boundary": "external"}, "network_boundary must be NetworkBoundary"),
        ({"level": "RUNTIME_OBSERVED"}, "level must be CapabilityEvidenceLevel"),
    ],
)
def test_invalid_evidence_subject_values_fail_closed(
    overrides: dict[str, object],
    message: str,
) -> None:
    values: dict[str, object] = {
        "provider_id": "mistral_external",
        "model": "ministral-8b-2512",
        "capability": ProviderCapability.TEXT,
        "network_boundary": NetworkBoundary.EXTERNAL,
        "level": CapabilityEvidenceLevel.CONFIGURED,
    }
    values.update(overrides)

    with pytest.raises(ValueError, match=message):
        CapabilityEvidence(**values)  # type: ignore[arg-type]
