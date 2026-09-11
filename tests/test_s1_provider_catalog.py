from dataclasses import FrozenInstanceError, fields

import pytest

from ai_core.provider_catalog import (
    CANONICAL_PROVIDER_IDS,
    PROVIDER_GPU_OLLAMA,
    PROVIDER_MISTRAL_EXTERNAL,
    PROVIDER_OLLAMA_CLOUD,
    PROVIDER_VM100_LOCAL_OLLAMA,
    NetworkBoundary,
    ProviderIdentity,
    UnknownProviderIdentityError,
    get_provider_catalog,
    get_provider_identity,
)


EXPECTED_PROVIDER_IDS = (
    "vm100_local_ollama",
    "gpu_ollama",
    "ollama_cloud",
    "mistral_external",
)


def test_canonical_provider_ids_are_exactly_the_governed_four() -> None:
    assert CANONICAL_PROVIDER_IDS == EXPECTED_PROVIDER_IDS
    assert (
        PROVIDER_VM100_LOCAL_OLLAMA,
        PROVIDER_GPU_OLLAMA,
        PROVIDER_OLLAMA_CLOUD,
        PROVIDER_MISTRAL_EXTERNAL,
    ) == EXPECTED_PROVIDER_IDS


def test_catalog_contains_only_identity_and_network_boundary_metadata() -> None:
    catalog = get_provider_catalog()

    assert tuple(catalog) == EXPECTED_PROVIDER_IDS
    assert [field.name for field in fields(ProviderIdentity)] == [
        "provider_id",
        "network_boundary",
    ]
    assert catalog["vm100_local_ollama"].network_boundary is (
        NetworkBoundary.LOCAL_SAME_HOST
    )
    assert catalog["gpu_ollama"].network_boundary is (
        NetworkBoundary.UNKNOWN_BOUNDARY
    )
    assert catalog["ollama_cloud"].network_boundary is NetworkBoundary.EXTERNAL
    assert catalog["mistral_external"].network_boundary is NetworkBoundary.EXTERNAL


def test_catalog_and_identity_records_are_immutable() -> None:
    catalog = get_provider_catalog()

    with pytest.raises(TypeError):
        catalog["new_provider"] = ProviderIdentity(  # type: ignore[index]
            provider_id="new_provider",
            network_boundary=NetworkBoundary.EXTERNAL,
        )

    with pytest.raises(FrozenInstanceError):
        catalog["gpu_ollama"].network_boundary = (  # type: ignore[misc]
            NetworkBoundary.LOCAL_SAME_HOST
        )


def test_unknown_provider_identity_fails_closed() -> None:
    with pytest.raises(
        UnknownProviderIdentityError,
        match="Unknown provider identity: unknown_provider",
    ):
        get_provider_identity("unknown_provider")


def test_known_provider_lookup_returns_canonical_record() -> None:
    identity = get_provider_identity("gpu_ollama")

    assert identity is get_provider_catalog()["gpu_ollama"]
    assert identity.provider_id == "gpu_ollama"
    assert identity.network_boundary is NetworkBoundary.UNKNOWN_BOUNDARY
