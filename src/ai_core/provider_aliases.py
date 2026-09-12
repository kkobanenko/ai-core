"""Deterministic legacy provider alias contracts.

This module maps a fixed set of legacy alias strings to canonical provider IDs.
It intentionally contains no transport, endpoint, model, capability, health,
retry, fallback, routing, or runtime behavior.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from ai_core.provider_catalog import (
    CANONICAL_PROVIDER_IDS,
    PROVIDER_GPU_OLLAMA,
    PROVIDER_MISTRAL_EXTERNAL,
    PROVIDER_VM100_LOCAL_OLLAMA,
)

# Ровно пять авторизованных legacy-алиасов; generic ``ollama`` сюда не входит.
_ALIAS_OLLAMA_LOCAL = "ollama_local"
_ALIAS_LOCAL_GPU_OLLAMA = "local_gpu_ollama"
_ALIAS_LOCAL_GPU_VISION = "local_gpu_vision"
_ALIAS_MISTRAL = "mistral"
_ALIAS_MISTRAL_OCR = "mistral_ocr"

_PROVIDER_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        _ALIAS_OLLAMA_LOCAL: PROVIDER_VM100_LOCAL_OLLAMA,
        _ALIAS_LOCAL_GPU_OLLAMA: PROVIDER_GPU_OLLAMA,
        _ALIAS_LOCAL_GPU_VISION: PROVIDER_GPU_OLLAMA,
        _ALIAS_MISTRAL: PROVIDER_MISTRAL_EXTERNAL,
        _ALIAS_MISTRAL_OCR: PROVIDER_MISTRAL_EXTERNAL,
    }
)


class UnknownProviderAliasError(KeyError):
    """Fail-closed ошибка: значение не канонический ID и не известный alias."""


def get_provider_aliases() -> Mapping[str, str]:
    """Return the immutable legacy alias-to-canonical-ID mapping."""

    return _PROVIDER_ALIASES


def resolve_provider_id(value: str) -> str:
    """Resolve a canonical provider ID or authorized legacy alias.

    Canonical IDs pass through unchanged. Unknown values fail closed.
    """

    # Шаг 1: канонический ID возвращаем без изменений (это не alias-маппинг).
    if value in CANONICAL_PROVIDER_IDS:
        return value

    # Шаг 2: точное совпадение с одним из пяти авторизованных alias.
    try:
        return _PROVIDER_ALIASES[value]
    except KeyError:
        # Шаг 3: всё остальное, включая generic ``ollama``, отклоняем.
        raise UnknownProviderAliasError(
            f"Unknown provider alias or identity: {value}"
        ) from None


__all__ = [
    "UnknownProviderAliasError",
    "get_provider_aliases",
    "resolve_provider_id",
]
