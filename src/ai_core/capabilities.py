"""Model-specific AI capabilities with lightweight evidence metadata.

Capabilities belong to the (provider_id, model) pair, not to the provider as a
whole. Unknown models are intentionally not assumed to support multimodal,
structured output, OCR, or speech-to-text.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ai_core.provider_catalog import (
    PROVIDER_DEEPSEEK_EXTERNAL,
    PROVIDER_GPU_OLLAMA,
    PROVIDER_GPU_WHISPER,
    PROVIDER_MISTRAL_EXTERNAL,
    PROVIDER_OLLAMA_CLOUD,
    PROVIDER_OPENAI_EXTERNAL,
    PROVIDER_VM100_LOCAL_OLLAMA,
)


class ProviderCapability(str, Enum):
    TEXT = "text"
    STRUCTURED_JSON = "structured_json"
    VISION_IMAGE = "vision_image"
    OCR_PDF = "ocr_pdf"
    STT_SEGMENTS = "stt_segments"


class ModelEvidenceLevel(str, Enum):
    """How strongly a model/capability declaration is supported."""

    HISTORICAL_PROVEN = "historical_proven"
    CURRENT_OBSERVED = "current_observed"


@dataclass(frozen=True)
class ProviderModelProfile:
    provider_id: str
    model: str
    capabilities: frozenset[ProviderCapability]
    evidence_level: ModelEvidenceLevel = ModelEvidenceLevel.HISTORICAL_PROVEN
    evidence_refs: tuple[str, ...] = ()


_MODEL_PROFILES: dict[tuple[str, str], ProviderModelProfile] = {
    # Historical ai-core v0.2.2 evidence.
    (PROVIDER_GPU_OLLAMA, "qwen2.5vl:7b"): ProviderModelProfile(
        provider_id=PROVIDER_GPU_OLLAMA,
        model="qwen2.5vl:7b",
        capabilities=frozenset({ProviderCapability.VISION_IMAGE, ProviderCapability.TEXT}),
        evidence_refs=("ai-core:v0.2.2",),
    ),
    (PROVIDER_MISTRAL_EXTERNAL, "mistral-ocr-latest"): ProviderModelProfile(
        provider_id=PROVIDER_MISTRAL_EXTERNAL,
        model="mistral-ocr-latest",
        capabilities=frozenset({ProviderCapability.OCR_PDF}),
        evidence_refs=("ai-core:v0.2.2", "prozakupki-platform:main/config/ai_providers.yaml"),
        evidence_level=ModelEvidenceLevel.CURRENT_OBSERVED,
    ),
    (PROVIDER_GPU_OLLAMA, "qwen3.5:9b"): ProviderModelProfile(
        provider_id=PROVIDER_GPU_OLLAMA,
        model="qwen3.5:9b",
        capabilities=frozenset({ProviderCapability.TEXT, ProviderCapability.STRUCTURED_JSON}),
        evidence_refs=("ai-core:v0.2.2",),
    ),
    (PROVIDER_MISTRAL_EXTERNAL, "ministral-8b-2512"): ProviderModelProfile(
        provider_id=PROVIDER_MISTRAL_EXTERNAL,
        model="ministral-8b-2512",
        capabilities=frozenset(
            {
                ProviderCapability.TEXT,
                ProviderCapability.STRUCTURED_JSON,
                ProviderCapability.VISION_IMAGE,
            }
        ),
        evidence_level=ModelEvidenceLevel.CURRENT_OBSERVED,
        evidence_refs=(
            "ai-core:v0.2.2:text_json",
            "prozakupki-platform:main/config/ai_providers.yaml:image_description",
        ),
    ),
    # Current consumer-observed models. These declarations reflect configured
    # capabilities, not a promise that every deployment has the model installed.
    (PROVIDER_GPU_OLLAMA, "qwen3.6:35b"): ProviderModelProfile(
        provider_id=PROVIDER_GPU_OLLAMA,
        model="qwen3.6:35b",
        capabilities=frozenset({ProviderCapability.TEXT, ProviderCapability.STRUCTURED_JSON}),
        evidence_level=ModelEvidenceLevel.CURRENT_OBSERVED,
        evidence_refs=(
            "prozakupki-platform:main/config/ai_providers.yaml:local_gpu_ollama",
            "kmo:main/services/operations-service/config/ai_providers.yaml:local_gpu_ollama",
        ),
    ),
    (PROVIDER_GPU_OLLAMA, "qwen3-vl:4b"): ProviderModelProfile(
        provider_id=PROVIDER_GPU_OLLAMA,
        model="qwen3-vl:4b",
        capabilities=frozenset({ProviderCapability.TEXT, ProviderCapability.VISION_IMAGE}),
        evidence_level=ModelEvidenceLevel.CURRENT_OBSERVED,
        evidence_refs=("prozakupki-platform:main/config/ai_providers.yaml:local_gpu_vision",),
    ),
    (PROVIDER_GPU_WHISPER, "Systran/faster-whisper-large-v3"): ProviderModelProfile(
        provider_id=PROVIDER_GPU_WHISPER,
        model="Systran/faster-whisper-large-v3",
        capabilities=frozenset({ProviderCapability.STT_SEGMENTS}),
        evidence_level=ModelEvidenceLevel.CURRENT_OBSERVED,
        evidence_refs=("prozakupki-platform:main/config/ai_providers.yaml:local_gpu_whisper",),
    ),
    (PROVIDER_VM100_LOCAL_OLLAMA, "qwen3.5:9b"): ProviderModelProfile(
        provider_id=PROVIDER_VM100_LOCAL_OLLAMA,
        model="qwen3.5:9b",
        capabilities=frozenset({ProviderCapability.TEXT, ProviderCapability.STRUCTURED_JSON}),
        evidence_level=ModelEvidenceLevel.CURRENT_OBSERVED,
        evidence_refs=(
            "prozakupki-platform:main/config/ai_providers.yaml:ollama_local",
            "kmo:main/services/operations-service/config/ai_providers.yaml:ollama_local",
        ),
    ),
    (PROVIDER_OLLAMA_CLOUD, "gemma4"): ProviderModelProfile(
        provider_id=PROVIDER_OLLAMA_CLOUD,
        model="gemma4",
        capabilities=frozenset({ProviderCapability.TEXT, ProviderCapability.STRUCTURED_JSON}),
        evidence_level=ModelEvidenceLevel.CURRENT_OBSERVED,
        evidence_refs=(
            "prozakupki-platform:main/config/ai_providers.yaml:ollama_cloud",
            "kmo:main/services/operations-service/config/ai_providers.yaml:ollama_cloud",
        ),
    ),
    (PROVIDER_OPENAI_EXTERNAL, "gpt-4o-mini-2024-07-18"): ProviderModelProfile(
        provider_id=PROVIDER_OPENAI_EXTERNAL,
        model="gpt-4o-mini-2024-07-18",
        capabilities=frozenset({ProviderCapability.TEXT, ProviderCapability.STRUCTURED_JSON}),
        evidence_level=ModelEvidenceLevel.CURRENT_OBSERVED,
        evidence_refs=("prozakupki-platform:main/config/ai_providers.yaml:openai",),
    ),
    (PROVIDER_OPENAI_EXTERNAL, "whisper-1"): ProviderModelProfile(
        provider_id=PROVIDER_OPENAI_EXTERNAL,
        model="whisper-1",
        capabilities=frozenset({ProviderCapability.STT_SEGMENTS}),
        evidence_level=ModelEvidenceLevel.CURRENT_OBSERVED,
        evidence_refs=("prozakupki-platform:main/config/ai_providers.yaml:openai/stt_default_model",),
    ),
    (PROVIDER_MISTRAL_EXTERNAL, "voxtral-mini-latest"): ProviderModelProfile(
        provider_id=PROVIDER_MISTRAL_EXTERNAL,
        model="voxtral-mini-latest",
        capabilities=frozenset({ProviderCapability.STT_SEGMENTS}),
        evidence_level=ModelEvidenceLevel.CURRENT_OBSERVED,
        evidence_refs=("prozakupki-platform:main/config/ai_providers.yaml:mistral/stt_default_model",),
    ),
    (PROVIDER_DEEPSEEK_EXTERNAL, "deepseek-chat"): ProviderModelProfile(
        provider_id=PROVIDER_DEEPSEEK_EXTERNAL,
        model="deepseek-chat",
        capabilities=frozenset({ProviderCapability.TEXT, ProviderCapability.STRUCTURED_JSON}),
        evidence_level=ModelEvidenceLevel.CURRENT_OBSERVED,
        evidence_refs=("prozakupki-platform:main/config/ai_providers.yaml:deepseek",),
    ),
}


def get_model_profile(provider_id: str, model: str) -> ProviderModelProfile | None:
    return _MODEL_PROFILES.get((provider_id, model))


def model_has_capability(
    provider_id: str,
    model: str,
    capability: ProviderCapability,
) -> bool:
    profile = get_model_profile(provider_id, model)
    return profile is not None and capability in profile.capabilities


def require_model_capability(
    provider_id: str,
    model: str,
    capability: ProviderCapability,
) -> ProviderModelProfile:
    profile = get_model_profile(provider_id, model)
    if profile is None:
        raise ValueError(
            f"Unknown model profile for provider={provider_id!r} model={model!r}; "
            "capabilities are not assumed for unknown models"
        )
    if capability not in profile.capabilities:
        raise ValueError(
            f"Model {model!r} on {provider_id!r} lacks capability {capability.value}"
        )
    return profile


def list_model_profiles() -> tuple[ProviderModelProfile, ...]:
    return tuple(_MODEL_PROFILES.values())
