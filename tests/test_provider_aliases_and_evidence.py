import pytest

from ai_core.capabilities import (
    ModelEvidenceLevel,
    ProviderCapability,
    get_model_profile,
    model_has_capability,
)
from ai_core.provider_aliases import (
    AmbiguousProviderAliasError,
    UnknownProviderAliasError,
    resolve_provider_id,
)


def test_consumer_aliases_resolve_to_canonical_network_identities():
    assert resolve_provider_id("ollama_local") == "vm100_local_ollama"
    assert resolve_provider_id("local_gpu_ollama") == "gpu_ollama"
    assert resolve_provider_id("local_gpu_vision") == "gpu_ollama"
    assert resolve_provider_id("local_gpu_whisper") == "gpu_whisper"
    assert resolve_provider_id("mistral") == "mistral_external"
    assert resolve_provider_id("mistral_ocr") == "mistral_external"
    assert resolve_provider_id("openai") == "openai_external"
    assert resolve_provider_id("deepseek") == "deepseek_external"


def test_canonical_ids_are_idempotent():
    assert resolve_provider_id("gpu_ollama") == "gpu_ollama"
    assert resolve_provider_id("mistral_external") == "mistral_external"


def test_generic_ollama_alias_is_deliberately_ambiguous():
    with pytest.raises(AmbiguousProviderAliasError):
        resolve_provider_id("ollama")


def test_unknown_or_test_local_names_do_not_silently_route():
    with pytest.raises(UnknownProviderAliasError):
        resolve_provider_id("fake")
    with pytest.raises(UnknownProviderAliasError):
        resolve_provider_id("some-new-provider")


def test_current_gpu_chat_and_vision_models_have_explicit_capabilities():
    assert model_has_capability(
        "gpu_ollama", "qwen3.6:35b", ProviderCapability.STRUCTURED_JSON
    )
    assert model_has_capability(
        "gpu_ollama", "qwen3-vl:4b", ProviderCapability.VISION_IMAGE
    )
    assert not model_has_capability(
        "gpu_ollama", "qwen3.6:35b", ProviderCapability.VISION_IMAGE
    )


def test_stt_is_a_first_class_model_capability():
    assert model_has_capability(
        "gpu_whisper",
        "Systran/faster-whisper-large-v3",
        ProviderCapability.STT_SEGMENTS,
    )
    assert model_has_capability(
        "openai_external", "whisper-1", ProviderCapability.STT_SEGMENTS
    )
    assert model_has_capability(
        "mistral_external", "voxtral-mini-latest", ProviderCapability.STT_SEGMENTS
    )


def test_current_observed_profiles_carry_non_secret_evidence_refs():
    profile = get_model_profile("gpu_ollama", "qwen3.6:35b")
    assert profile is not None
    assert profile.evidence_level == ModelEvidenceLevel.CURRENT_OBSERVED
    assert profile.evidence_refs
    blob = " ".join(profile.evidence_refs)
    assert "prozakupki-platform" in blob
    assert "sk-" not in blob
    assert "Bearer " not in blob
