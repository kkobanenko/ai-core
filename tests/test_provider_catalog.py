"""Каталог: четыре раздельные идентичности провайдеров."""

from ai_core.provider_catalog import (
    CANONICAL_PROVIDER_IDS,
    NetworkBoundary,
    PiiPolicy,
    get_provider_catalog,
    get_provider_profile,
)


def test_four_canonical_provider_ids_are_distinct():
    catalog = get_provider_catalog()
    assert set(catalog.keys()) == set(CANONICAL_PROVIDER_IDS)
    assert len(CANONICAL_PROVIDER_IDS) == 4
    assert len(set(CANONICAL_PROVIDER_IDS)) == 4


def test_vm100_local_allows_raw_and_is_local_boundary():
    profile = get_provider_profile("vm100_local_ollama")
    assert profile.network_boundary == NetworkBoundary.LOCAL_SAME_HOST
    assert profile.raw_pii_policy == PiiPolicy.ALLOW
    assert "OLLAMA_HOST" in profile.endpoint_env_keys or profile.endpoint_env_keys


def test_ollama_cloud_is_external_and_denies_raw():
    profile = get_provider_profile("ollama_cloud")
    assert profile.network_boundary == NetworkBoundary.EXTERNAL_CLOUD
    assert profile.raw_pii_policy == PiiPolicy.DENY
    assert profile.sanitized_pii_policy == PiiPolicy.ALLOW
    assert "OLLAMA_API_KEY" in profile.credential_env_keys


def test_gpu_ollama_unknown_boundary_denies_raw():
    profile = get_provider_profile("gpu_ollama")
    assert profile.network_boundary == NetworkBoundary.UNKNOWN_BOUNDARY
    assert profile.raw_pii_policy == PiiPolicy.DENY
    assert "local_gpu_ollama" in profile.historical_names


def test_mistral_external_is_separate_identity():
    profile = get_provider_profile("mistral_external")
    assert profile.provider_id == "mistral_external"
    assert profile.network_boundary == NetworkBoundary.EXTERNAL_CLOUD
    assert profile.raw_pii_policy == PiiPolicy.DENY
    assert "MISTRAL_API_KEY" in profile.credential_env_keys
    # Не путать с ollama_cloud
    assert profile.provider_id != "ollama_cloud"


def test_catalog_has_no_secret_values_in_profiles():
    """В профилях только имена ключей, не значения вроде sk-..."""
    for profile in get_provider_catalog().values():
        blob = " ".join(profile.credential_env_keys + profile.endpoint_env_keys)
        assert "sk-" not in blob
        assert "Bearer" not in blob
