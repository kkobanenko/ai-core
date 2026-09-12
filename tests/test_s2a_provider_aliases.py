import inspect

import pytest

from ai_core.provider_aliases import (
    UnknownProviderAliasError,
    get_provider_aliases,
    resolve_provider_id,
)
from ai_core.provider_catalog import (
    CANONICAL_PROVIDER_IDS,
    PROVIDER_GPU_OLLAMA,
    PROVIDER_MISTRAL_EXTERNAL,
    PROVIDER_VM100_LOCAL_OLLAMA,
)


AUTHORIZED_ALIAS_MAP = {
    "ollama_local": PROVIDER_VM100_LOCAL_OLLAMA,
    "local_gpu_ollama": PROVIDER_GPU_OLLAMA,
    "local_gpu_vision": PROVIDER_GPU_OLLAMA,
    "mistral": PROVIDER_MISTRAL_EXTERNAL,
    "mistral_ocr": PROVIDER_MISTRAL_EXTERNAL,
}


def test_alias_map_contains_exactly_five_authorized_mappings() -> None:
    aliases = get_provider_aliases()

    assert len(aliases) == 5
    assert dict(aliases) == AUTHORIZED_ALIAS_MAP


def test_alias_map_is_immutable() -> None:
    aliases = get_provider_aliases()

    with pytest.raises(TypeError):
        aliases["ollama_local"] = PROVIDER_GPU_OLLAMA  # type: ignore[index]


@pytest.mark.parametrize(
    ("alias", "expected"),
    AUTHORIZED_ALIAS_MAP.items(),
)
def test_authorized_aliases_resolve_to_expected_canonical_ids(
    alias: str,
    expected: str,
) -> None:
    assert resolve_provider_id(alias) == expected


@pytest.mark.parametrize("canonical_id", CANONICAL_PROVIDER_IDS)
def test_canonical_provider_ids_pass_through_unchanged(canonical_id: str) -> None:
    assert resolve_provider_id(canonical_id) == canonical_id


def test_generic_ollama_fails_closed() -> None:
    with pytest.raises(
        UnknownProviderAliasError,
        match="Unknown provider alias or identity: ollama",
    ):
        resolve_provider_id("ollama")


@pytest.mark.parametrize(
    "unknown_value",
    [
        "",
        "unknown_provider",
        "ollama_cloud_alias",
    ],
)
def test_empty_and_unknown_values_fail_closed(unknown_value: str) -> None:
    with pytest.raises(
        UnknownProviderAliasError,
        match=f"Unknown provider alias or identity: {unknown_value}",
    ):
        resolve_provider_id(unknown_value)


@pytest.mark.parametrize(
    "near_miss",
    [
        "OLLAMA_LOCAL",
        " ollama_local",
        "ollama_local ",
        " Local_Gpu_Ollama",
        "mistral ",
    ],
)
def test_near_miss_variants_do_not_normalize_silently(near_miss: str) -> None:
    with pytest.raises(UnknownProviderAliasError):
        resolve_provider_id(near_miss)


def test_every_successful_resolution_is_a_canonical_provider_id() -> None:
    for alias in AUTHORIZED_ALIAS_MAP:
        resolved = resolve_provider_id(alias)
        assert resolved in CANONICAL_PROVIDER_IDS

    for canonical_id in CANONICAL_PROVIDER_IDS:
        resolved = resolve_provider_id(canonical_id)
        assert resolved in CANONICAL_PROVIDER_IDS


def test_module_api_exposes_only_alias_contract_symbols() -> None:
    from ai_core import provider_aliases

    assert provider_aliases.__all__ == [
        "UnknownProviderAliasError",
        "get_provider_aliases",
        "resolve_provider_id",
    ]


def test_module_does_not_encode_model_capability_or_runtime_semantics() -> None:
    source = inspect.getsource(get_provider_aliases)
    assert "model" not in source.lower()
    assert "capability" not in source.lower()
    assert "route" not in source.lower()
    assert "health" not in source.lower()
    assert "retry" not in source.lower()
    assert "fallback" not in source.lower()
    assert "transport" not in source.lower()

    aliases = get_provider_aliases()
    for alias, canonical_id in aliases.items():
        assert isinstance(alias, str)
        assert isinstance(canonical_id, str)
        assert canonical_id in CANONICAL_PROVIDER_IDS
