"""Общая библиотека Phoenix tracing, provider policy и IO-политики для AI-проектов."""

from ai_core.attributes import AttributeValue, sanitize_attributes
from ai_core.capabilities import (
    ProviderCapability,
    ProviderModelProfile,
    get_model_profile,
    list_model_profiles,
    model_has_capability,
    require_model_capability,
)
from ai_core.config import PhoenixConfig, load_phoenix_config
from ai_core.io_policy import maybe_truncate
from ai_core.privacy import DataClass, OutboundForm, is_eligible_for_outbound
from ai_core.provider_catalog import (
    CANONICAL_PROVIDER_IDS,
    BackendKind,
    NetworkBoundary,
    PiiPolicy,
    ProviderProfile,
    get_provider_catalog,
    get_provider_profile,
)
from ai_core.tracing import (
    init_tracing,
    record_llm_result,
    shutdown_tracing,
    start_llm_span,
)

__all__ = [
    "AttributeValue",
    "BackendKind",
    "CANONICAL_PROVIDER_IDS",
    "DataClass",
    "NetworkBoundary",
    "OutboundForm",
    "PhoenixConfig",
    "PiiPolicy",
    "ProviderCapability",
    "ProviderModelProfile",
    "ProviderProfile",
    "get_model_profile",
    "get_provider_catalog",
    "get_provider_profile",
    "init_tracing",
    "is_eligible_for_outbound",
    "list_model_profiles",
    "load_phoenix_config",
    "maybe_truncate",
    "model_has_capability",
    "record_llm_result",
    "require_model_capability",
    "sanitize_attributes",
    "shutdown_tracing",
    "start_llm_span",
]
