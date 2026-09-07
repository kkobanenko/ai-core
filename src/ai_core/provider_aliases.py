"""Explicit migration aliases from consumer-local provider names.

Aliases are intentionally conservative. Generic names that can point at more
than one network boundary must not be guessed.
"""

from __future__ import annotations

from ai_core.provider_catalog import (
    CANONICAL_PROVIDER_IDS,
    PROVIDER_DEEPSEEK_EXTERNAL,
    PROVIDER_GPU_OLLAMA,
    PROVIDER_GPU_WHISPER,
    PROVIDER_MISTRAL_EXTERNAL,
    PROVIDER_OPENAI_EXTERNAL,
    PROVIDER_VM100_LOCAL_OLLAMA,
)


class ProviderAliasError(ValueError):
    """Base class for provider-name reconciliation failures."""


class UnknownProviderAliasError(ProviderAliasError):
    """The supplied name has no canonical mapping."""


class AmbiguousProviderAliasError(ProviderAliasError):
    """The supplied name can refer to multiple network identities."""


_PROVIDER_ALIASES: dict[str, str] = {
    "ollama_local": PROVIDER_VM100_LOCAL_OLLAMA,
    "local_gpu_ollama": PROVIDER_GPU_OLLAMA,
    "local_gpu_vision": PROVIDER_GPU_OLLAMA,
    "local_gpu_whisper": PROVIDER_GPU_WHISPER,
    "mistral": PROVIDER_MISTRAL_EXTERNAL,
    "mistral_ocr": PROVIDER_MISTRAL_EXTERNAL,
    "openai": PROVIDER_OPENAI_EXTERNAL,
    "deepseek": PROVIDER_DEEPSEEK_EXTERNAL,
}

# `ollama` is used by different consumers for a local host/sidecar and therefore
# cannot be safely mapped to vm100_local_ollama or ollama_cloud without context.
_AMBIGUOUS_ALIASES = frozenset({"ollama"})


def get_provider_aliases() -> dict[str, str]:
    """Return a copy of explicitly approved migration aliases."""

    return dict(_PROVIDER_ALIASES)


def resolve_provider_id(name: str) -> str:
    """Resolve a canonical id or explicit legacy alias, failing closed otherwise."""

    normalized = str(name).strip().lower()
    if not normalized:
        raise UnknownProviderAliasError("provider name is empty")
    if normalized in CANONICAL_PROVIDER_IDS:
        return normalized
    if normalized in _AMBIGUOUS_ALIASES:
        raise AmbiguousProviderAliasError(
            f"Provider alias {normalized!r} is ambiguous; choose an explicit canonical provider id"
        )
    try:
        return _PROVIDER_ALIASES[normalized]
    except KeyError as exc:
        raise UnknownProviderAliasError(f"Unknown provider alias: {normalized}") from exc
