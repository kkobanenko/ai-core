"""Каталог: четыре раздельные идентичности провайдеров."""

from ai_core.provider_catalog import (
    CANONICAL_PROVIDER_IDS,
    BackendKind,
    CostClass,
    HealthProbeKind,
    LatencyClass,
    NetworkBoundary,
    PiiPolicy,
    ProviderProfile,
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


def test_provider_profile_v021_constructor_compatible_without_api_key_optional():
    """v0.2.1 public constructor fields must still construct; default api_key_optional=False."""
    profile = ProviderProfile(
        provider_id="test",
        backend_kind=BackendKind.OLLAMA,
        network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
        raw_pii_policy=PiiPolicy.ALLOW,
        sanitized_pii_policy=PiiPolicy.ALLOW,
        supports_structured_json=True,
        supports_text=True,
        supports_multimodal=False,
        health_probe_kind=HealthProbeKind.NONE,
        cost_class=CostClass.UNKNOWN,
        latency_class=LatencyClass.UNKNOWN,
        priority_hint=100,
        endpoint_env_keys=(),
        credential_env_keys=(),
        default_model_env="TEST_MODEL",
        historical_names=(),
    )
    assert profile.api_key_optional is False
    assert profile.endpoint_default_scheme == ""
    assert profile.endpoint_default_port is None


def test_builtin_api_key_optional_explicit_values():
    assert get_provider_profile("vm100_local_ollama").api_key_optional is True
    assert get_provider_profile("gpu_ollama").api_key_optional is True
    assert get_provider_profile("ollama_cloud").api_key_optional is False
    assert get_provider_profile("mistral_external").api_key_optional is False
    assert "AI_PROVIDER" not in get_provider_profile("ollama_cloud").credential_env_keys
