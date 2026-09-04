"""Общая библиотека Phoenix tracing, IO-политики и privacy-aware провайдеров."""

from ai_core.capabilities import (
    ProviderCapability,
    ProviderModelProfile,
    get_model_profile,
    list_model_profiles,
    model_has_capability,
    require_model_capability,
)
from ai_core.config import PhoenixConfig, load_phoenix_config
from ai_core.dlp import DlpDecision, DlpResult, is_egress_allowed, outbound_leak_check
from ai_core.health import (
    ProviderHealthStatus,
    ProviderHealthStore,
    mark_quota_limited,
    probe_ollama_tags,
    probe_ollama_tags_for_provider,
)
from ai_core.io_policy import maybe_truncate
from ai_core.json_client import LangChainJsonClient, ProviderTransportError
from ai_core.media import MediaResult, OcrPdfRequest, VisionImageRequest
from ai_core.media_errors import MediaAuthError, MediaTransportError
from ai_core.media_gate import MediaPrivacyError, assert_media_allowed
from ai_core.models import AttemptRecord, JsonCompletion, ProviderConfig
from ai_core.ocr_pdf import build_mistral_ocr_payload, invoke_pdf_ocr
from ai_core.privacy import (
    DataClass,
    OutboundForm,
    is_eligible_for_outbound,
    is_sensitive_data_class,
)
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
from ai_core.provider_factory import build_chat_model
from ai_core.resolve import ResolvedProviderEndpoint, resolve_provider_endpoint
from ai_core.routing import PrivacyAwareRouter, RawRouteExhaustedError
from ai_core.surrogate import (
    EntityKind,
    SecretAction,
    SurrogateMode,
    SurrogateResult,
    apply_surrogate,
    clear_local_map,
    detect_entities,
)
from ai_core.tracing import init_tracing, shutdown_tracing, start_llm_span
from ai_core.vision import build_ollama_vision_payload, invoke_vision

__all__ = [
    # v0.2.0 symbols (совместимость)
    "AttemptRecord",
    "build_chat_model",
    "JsonCompletion",
    "LangChainJsonClient",
    "PhoenixConfig",
    "ProviderConfig",
    "ProviderTransportError",
    "load_phoenix_config",
    "init_tracing",
    "maybe_truncate",
    "shutdown_tracing",
    "start_llm_span",
    # v0.2.1 additive: catalog
    "BackendKind",
    "CANONICAL_PROVIDER_IDS",
    "CostClass",
    "HealthProbeKind",
    "LatencyClass",
    "NetworkBoundary",
    "PiiPolicy",
    "ProviderProfile",
    "get_provider_catalog",
    "get_provider_profile",
    # privacy
    "DataClass",
    "OutboundForm",
    "is_eligible_for_outbound",
    "is_sensitive_data_class",
    # surrogate
    "EntityKind",
    "SecretAction",
    "SurrogateMode",
    "SurrogateResult",
    "apply_surrogate",
    "clear_local_map",
    "detect_entities",
    # dlp
    "DlpDecision",
    "DlpResult",
    "is_egress_allowed",
    "outbound_leak_check",
    # routing
    "PrivacyAwareRouter",
    "RawRouteExhaustedError",
    # health
    "ProviderHealthStatus",
    "ProviderHealthStore",
    "mark_quota_limited",
    "probe_ollama_tags",
    "probe_ollama_tags_for_provider",
    # AU01B multimodal / OCR (additive)
    "ProviderCapability",
    "ProviderModelProfile",
    "get_model_profile",
    "list_model_profiles",
    "model_has_capability",
    "require_model_capability",
    "VisionImageRequest",
    "OcrPdfRequest",
    "MediaResult",
    "MediaAuthError",
    "MediaTransportError",
    "MediaPrivacyError",
    "assert_media_allowed",
    "ResolvedProviderEndpoint",
    "resolve_provider_endpoint",
    "build_ollama_vision_payload",
    "invoke_vision",
    "build_mistral_ocr_payload",
    "invoke_pdf_ocr",
]
