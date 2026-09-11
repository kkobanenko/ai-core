"""Pure, model-scoped capability evidence contracts.

Evidence records describe what was observed. They do not authorize production
routing or provider execution; those require separate policy gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ai_core.provider_catalog import NetworkBoundary, get_provider_identity


class ProviderCapability(str, Enum):
    """Capability vocabulary allowed in the S1 foundation contract."""

    TEXT = "text"
    STRUCTURED_JSON = "structured_json"
    VISION_IMAGE = "vision_image"
    OCR_PDF = "ocr_pdf"


class CapabilityEvidenceLevel(str, Enum):
    """Governed evidence levels without implicit capability promotion."""

    CONFIGURED = "CONFIGURED"
    UNIT_TESTED = "UNIT_TESTED"
    INTEGRATION_TESTED = "INTEGRATION_TESTED"
    RUNTIME_OBSERVED = "RUNTIME_OBSERVED"
    FAILED_INCONCLUSIVE = "FAILED_INCONCLUSIVE"


@dataclass(frozen=True)
class CapabilityEvidence:
    """Evidence for one provider, model, capability, and network boundary."""

    provider_id: str
    model: str
    capability: ProviderCapability
    network_boundary: NetworkBoundary
    level: CapabilityEvidenceLevel

    def __post_init__(self) -> None:
        if not isinstance(self.provider_id, str) or not self.provider_id.strip():
            raise ValueError("provider_id must be a non-empty string")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be a non-empty string")
        if not isinstance(self.capability, ProviderCapability):
            raise ValueError("capability must be ProviderCapability")
        if not isinstance(self.network_boundary, NetworkBoundary):
            raise ValueError("network_boundary must be NetworkBoundary")
        if not isinstance(self.level, CapabilityEvidenceLevel):
            raise ValueError("level must be CapabilityEvidenceLevel")

        identity = get_provider_identity(self.provider_id)
        if self.network_boundary is not identity.network_boundary:
            raise ValueError(
                f"Boundary mismatch for {self.provider_id}: "
                f"governed={identity.network_boundary.value} "
                f"evidence={self.network_boundary.value}"
            )


def has_runtime_observation(evidence: CapabilityEvidence) -> bool:
    """Return whether this record is an actual runtime observation.

    A true result is evidence only. It is not routing eligibility and does not
    replace privacy, identity, health, or governance gates.
    """

    return evidence.level is CapabilityEvidenceLevel.RUNTIME_OBSERVED


__all__ = [
    "CapabilityEvidence",
    "CapabilityEvidenceLevel",
    "ProviderCapability",
    "has_runtime_observation",
]
