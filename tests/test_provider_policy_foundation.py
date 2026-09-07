from ai_core.capabilities import (
    ProviderCapability,
    model_has_capability,
    require_model_capability,
)
from ai_core.privacy import DataClass, OutboundForm, is_eligible_for_outbound
from ai_core.provider_catalog import (
    NetworkBoundary,
    PiiPolicy,
    get_provider_catalog,
    get_provider_profile,
)


def test_catalog_keeps_provider_identities_separate_and_secret_free():
    catalog = get_provider_catalog()
    assert set(catalog) == {
        "vm100_local_ollama",
        "ollama_cloud",
        "gpu_ollama",
        "gpu_whisper",
        "mistral_external",
        "openai_external",
        "deepseek_external",
    }

    assert catalog["vm100_local_ollama"].network_boundary == NetworkBoundary.LOCAL_SAME_HOST
    assert catalog["ollama_cloud"].network_boundary == NetworkBoundary.EXTERNAL_CLOUD
    assert catalog["gpu_ollama"].network_boundary == NetworkBoundary.UNKNOWN_BOUNDARY
    assert catalog["gpu_whisper"].network_boundary == NetworkBoundary.UNKNOWN_BOUNDARY
    assert catalog["mistral_external"].network_boundary == NetworkBoundary.EXTERNAL_CLOUD
    assert catalog["openai_external"].network_boundary == NetworkBoundary.EXTERNAL_CLOUD
    assert catalog["deepseek_external"].network_boundary == NetworkBoundary.EXTERNAL_CLOUD

    for profile in catalog.values():
        names_only = " ".join(profile.endpoint_env_keys + profile.credential_env_keys)
        assert "sk-" not in names_only
        assert "Bearer " not in names_only


def test_sensitive_raw_fails_closed_for_external_and_unknown_boundaries():
    private = DataClass.PRIVATE_CLIENT_DATA
    raw = OutboundForm.RAW

    assert is_eligible_for_outbound(get_provider_profile("vm100_local_ollama"), private, raw)
    for provider_id in (
        "ollama_cloud",
        "gpu_ollama",
        "gpu_whisper",
        "mistral_external",
        "openai_external",
        "deepseek_external",
    ):
        assert not is_eligible_for_outbound(get_provider_profile(provider_id), private, raw)


def test_secret_raw_is_blocked_even_for_local_provider():
    local = get_provider_profile("vm100_local_ollama")
    assert local.raw_pii_policy == PiiPolicy.ALLOW
    assert not is_eligible_for_outbound(local, DataClass.SECRET, OutboundForm.RAW)


def test_sanitized_private_data_may_use_external_provider_when_policy_allows():
    external = get_provider_profile("mistral_external")
    assert is_eligible_for_outbound(
        external,
        DataClass.PRIVATE_CLIENT_DATA,
        OutboundForm.SANITIZED,
    )


def test_model_capabilities_are_explicit_and_unknown_models_fail_closed():
    assert model_has_capability(
        "mistral_external",
        "ministral-8b-2512",
        ProviderCapability.STRUCTURED_JSON,
    )
    assert not model_has_capability(
        "mistral_external",
        "ministral-8b-2512",
        ProviderCapability.OCR_PDF,
    )
    assert not model_has_capability(
        "gpu_ollama",
        "unknown-model",
        ProviderCapability.VISION_IMAGE,
    )

    try:
        require_model_capability(
            "gpu_ollama",
            "unknown-model",
            ProviderCapability.VISION_IMAGE,
        )
    except ValueError as exc:
        assert "Unknown model profile" in str(exc)
    else:
        raise AssertionError("unknown model must fail closed")
