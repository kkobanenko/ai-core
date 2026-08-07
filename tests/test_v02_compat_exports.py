"""Совместимость: символы v0.2.0 по-прежнему импортируются."""


def test_v02_public_symbols_still_importable():
    from ai_core import (
        AttemptRecord,
        JsonCompletion,
        LangChainJsonClient,
        PhoenixConfig,
        ProviderConfig,
        ProviderTransportError,
        build_chat_model,
        init_tracing,
        load_phoenix_config,
        maybe_truncate,
        shutdown_tracing,
        start_llm_span,
    )

    assert ProviderConfig is not None
    assert build_chat_model is not None
    assert LangChainJsonClient is not None
    assert PhoenixConfig is not None
    assert load_phoenix_config is not None
    assert init_tracing is not None
    assert shutdown_tracing is not None
    assert start_llm_span is not None
    assert maybe_truncate is not None
    assert AttemptRecord is not None
    assert JsonCompletion is not None
    assert ProviderTransportError is not None


def test_new_v021_symbols_also_exported():
    from ai_core import (
        DataClass,
        OutboundForm,
        PrivacyAwareRouter,
        ProviderHealthStore,
        ProviderProfile,
        RawRouteExhaustedError,
        apply_surrogate,
        get_provider_catalog,
        outbound_leak_check,
    )

    assert get_provider_catalog
    assert ProviderProfile
    assert DataClass
    assert OutboundForm
    assert apply_surrogate
    assert outbound_leak_check
    assert PrivacyAwareRouter
    assert RawRouteExhaustedError
    assert ProviderHealthStore
