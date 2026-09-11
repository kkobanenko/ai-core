"""Canonical provider identity and trust-boundary contracts.

The catalog intentionally contains no transport, credential, endpoint, model,
health, cost, latency, priority, or capability behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class NetworkBoundary(str, Enum):
    """Governed network boundary for an accepted provider identity."""

    LOCAL_SAME_HOST = "local_same_host"
    EXTERNAL = "external"
    UNKNOWN_BOUNDARY = "unknown_boundary"


PROVIDER_VM100_LOCAL_OLLAMA = "vm100_local_ollama"
PROVIDER_GPU_OLLAMA = "gpu_ollama"
PROVIDER_OLLAMA_CLOUD = "ollama_cloud"
PROVIDER_MISTRAL_EXTERNAL = "mistral_external"

CANONICAL_PROVIDER_IDS = (
    PROVIDER_VM100_LOCAL_OLLAMA,
    PROVIDER_GPU_OLLAMA,
    PROVIDER_OLLAMA_CLOUD,
    PROVIDER_MISTRAL_EXTERNAL,
)


@dataclass(frozen=True)
class ProviderIdentity:
    """Immutable identity and its currently governed network boundary."""

    provider_id: str
    network_boundary: NetworkBoundary


class UnknownProviderIdentityError(KeyError):
    """Raised when a provider identity is outside the governed catalog."""


_PROVIDER_CATALOG: Mapping[str, ProviderIdentity] = MappingProxyType(
    {
        PROVIDER_VM100_LOCAL_OLLAMA: ProviderIdentity(
            provider_id=PROVIDER_VM100_LOCAL_OLLAMA,
            network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
        ),
        PROVIDER_GPU_OLLAMA: ProviderIdentity(
            provider_id=PROVIDER_GPU_OLLAMA,
            network_boundary=NetworkBoundary.UNKNOWN_BOUNDARY,
        ),
        PROVIDER_OLLAMA_CLOUD: ProviderIdentity(
            provider_id=PROVIDER_OLLAMA_CLOUD,
            network_boundary=NetworkBoundary.EXTERNAL,
        ),
        PROVIDER_MISTRAL_EXTERNAL: ProviderIdentity(
            provider_id=PROVIDER_MISTRAL_EXTERNAL,
            network_boundary=NetworkBoundary.EXTERNAL,
        ),
    }
)


def get_provider_catalog() -> Mapping[str, ProviderIdentity]:
    """Return the immutable canonical provider identity mapping."""

    return _PROVIDER_CATALOG


def get_provider_identity(provider_id: str) -> ProviderIdentity:
    """Return a governed identity, failing closed for every unknown ID."""

    try:
        return _PROVIDER_CATALOG[provider_id]
    except KeyError:
        raise UnknownProviderIdentityError(
            f"Unknown provider identity: {provider_id}"
        ) from None


__all__ = [
    "CANONICAL_PROVIDER_IDS",
    "PROVIDER_GPU_OLLAMA",
    "PROVIDER_MISTRAL_EXTERNAL",
    "PROVIDER_OLLAMA_CLOUD",
    "PROVIDER_VM100_LOCAL_OLLAMA",
    "NetworkBoundary",
    "ProviderIdentity",
    "UnknownProviderIdentityError",
    "get_provider_catalog",
    "get_provider_identity",
]
