"""Модельные capability: TEXT / STRUCTURED_JSON / VISION_IMAGE / OCR_PDF.

Capability привязана к (provider_id, model), а не ко всему ProviderProfile.
ProviderProfile.supports_multimodal намеренно НЕ переключается в True.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ai_core.provider_catalog import PROVIDER_GPU_OLLAMA, PROVIDER_MISTRAL_EXTERNAL


class ProviderCapability(str, Enum):
    """Заявленная capability конкретной модели у провайдера."""

    TEXT = "text"
    STRUCTURED_JSON = "structured_json"
    VISION_IMAGE = "vision_image"
    OCR_PDF = "ocr_pdf"


@dataclass(frozen=True)
class ProviderModelProfile:
    """Неизменяемый профиль конкретной модели (без секретов)."""

    provider_id: str
    model: str
    capabilities: frozenset[ProviderCapability]


# Минимальный registry только для доказанных моделей (не универсальный каталог).
_MODEL_PROFILES: dict[tuple[str, str], ProviderModelProfile] = {
    (
        PROVIDER_GPU_OLLAMA,
        "qwen2.5vl:7b",
    ): ProviderModelProfile(
        provider_id=PROVIDER_GPU_OLLAMA,
        model="qwen2.5vl:7b",
        capabilities=frozenset({ProviderCapability.VISION_IMAGE, ProviderCapability.TEXT}),
    ),
    (
        PROVIDER_MISTRAL_EXTERNAL,
        "mistral-ocr-latest",
    ): ProviderModelProfile(
        provider_id=PROVIDER_MISTRAL_EXTERNAL,
        model="mistral-ocr-latest",
        capabilities=frozenset({ProviderCapability.OCR_PDF}),
    ),
    # Явно текстовые — без VISION_IMAGE / OCR_PDF.
    (
        PROVIDER_GPU_OLLAMA,
        "qwen3.5:9b",
    ): ProviderModelProfile(
        provider_id=PROVIDER_GPU_OLLAMA,
        model="qwen3.5:9b",
        capabilities=frozenset({ProviderCapability.TEXT, ProviderCapability.STRUCTURED_JSON}),
    ),
    (
        PROVIDER_MISTRAL_EXTERNAL,
        "ministral-8b-2512",
    ): ProviderModelProfile(
        provider_id=PROVIDER_MISTRAL_EXTERNAL,
        model="ministral-8b-2512",
        capabilities=frozenset({ProviderCapability.TEXT, ProviderCapability.STRUCTURED_JSON}),
    ),
}


def get_model_profile(provider_id: str, model: str) -> ProviderModelProfile | None:
    """Lookup; неизвестная модель → None (не считаем multimodal)."""
    return _MODEL_PROFILES.get((provider_id, model))


def model_has_capability(
    provider_id: str,
    model: str,
    capability: ProviderCapability,
) -> bool:
    """True только если модель явно зарегистрирована с этой capability."""
    profile = get_model_profile(provider_id, model)
    if profile is None:
        return False
    return capability in profile.capabilities


def require_model_capability(
    provider_id: str,
    model: str,
    capability: ProviderCapability,
) -> ProviderModelProfile:
    """Проверить capability; неизвестная/неподходящая модель → ValueError."""
    profile = get_model_profile(provider_id, model)
    if profile is None:
        raise ValueError(
            f"Unknown model profile for provider={provider_id!r} model={model!r}; "
            "multimodal/OCR is not assumed for unknown models"
        )
    if capability not in profile.capabilities:
        raise ValueError(
            f"Model {model!r} on {provider_id!r} lacks capability {capability.value}"
        )
    return profile


def list_model_profiles() -> tuple[ProviderModelProfile, ...]:
    """Все зарегистрированные профили (для тестов/документации)."""
    return tuple(_MODEL_PROFILES.values())
