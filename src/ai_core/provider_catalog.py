"""Canonical AI provider catalog.

The catalog identifies provider/network boundaries. Model-specific modality lives
in :mod:`ai_core.capabilities`. The catalog stores environment variable *names*
only; credential values are resolved by transport layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NetworkBoundary(str, Enum):
    """Physical/network trust boundary for a provider."""

    LOCAL_SAME_HOST = "local_same_host"
    PRIVATE_TRUSTED_INFRA = "private_trusted_infra"
    EXTERNAL_CLOUD = "external_cloud"
    UNKNOWN_BOUNDARY = "unknown_boundary"


class PiiPolicy(str, Enum):
    """Whether a provider is allowed to receive PII in a given form."""

    ALLOW = "allow"
    DENY = "deny"


class BackendKind(str, Enum):
    """Provider transport/SDK family."""

    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"
    MISTRAL = "mistral"
    FASTER_WHISPER_HTTP = "faster_whisper_http"


class HealthProbeKind(str, Enum):
    """Read-only health probe type; payload content must never be sent."""

    OLLAMA_TAGS = "ollama_tags"
    NONE = "none"


class CostClass(str, Enum):
    FREE_LOCAL = "free_local"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class LatencyClass(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


PROVIDER_VM100_LOCAL_OLLAMA = "vm100_local_ollama"
PROVIDER_OLLAMA_CLOUD = "ollama_cloud"
PROVIDER_GPU_OLLAMA = "gpu_ollama"
PROVIDER_GPU_WHISPER = "gpu_whisper"
PROVIDER_MISTRAL_EXTERNAL = "mistral_external"
PROVIDER_OPENAI_EXTERNAL = "openai_external"
PROVIDER_DEEPSEEK_EXTERNAL = "deepseek_external"

CANONICAL_PROVIDER_IDS = (
    PROVIDER_VM100_LOCAL_OLLAMA,
    PROVIDER_OLLAMA_CLOUD,
    PROVIDER_GPU_OLLAMA,
    PROVIDER_GPU_WHISPER,
    PROVIDER_MISTRAL_EXTERNAL,
    PROVIDER_OPENAI_EXTERNAL,
    PROVIDER_DEEPSEEK_EXTERNAL,
)


@dataclass(frozen=True)
class ProviderProfile:
    """Immutable provider metadata; contains no credential values."""

    provider_id: str
    backend_kind: BackendKind
    network_boundary: NetworkBoundary
    raw_pii_policy: PiiPolicy
    sanitized_pii_policy: PiiPolicy
    supports_structured_json: bool
    supports_text: bool
    supports_multimodal: bool
    health_probe_kind: HealthProbeKind
    cost_class: CostClass
    latency_class: LatencyClass
    priority_hint: int
    endpoint_env_keys: tuple[str, ...]
    credential_env_keys: tuple[str, ...]
    default_model_env: str
    historical_names: tuple[str, ...]
    api_key_optional: bool = False
    endpoint_default_scheme: str = ""
    endpoint_default_port: int | None = None


def _build_catalog() -> dict[str, ProviderProfile]:
    return {
        PROVIDER_VM100_LOCAL_OLLAMA: ProviderProfile(
            provider_id=PROVIDER_VM100_LOCAL_OLLAMA,
            backend_kind=BackendKind.OLLAMA,
            network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
            raw_pii_policy=PiiPolicy.ALLOW,
            sanitized_pii_policy=PiiPolicy.ALLOW,
            supports_structured_json=True,
            supports_text=True,
            supports_multimodal=False,
            health_probe_kind=HealthProbeKind.OLLAMA_TAGS,
            cost_class=CostClass.FREE_LOCAL,
            latency_class=LatencyClass.LOW,
            priority_hint=10,
            endpoint_env_keys=("OLLAMA_HOST", "OLLAMA_BASE_URL"),
            credential_env_keys=(),
            default_model_env="OLLAMA_MODEL",
            historical_names=("ollama_local", "ollama sidecar", "127.0.0.1:11434"),
            api_key_optional=True,
            endpoint_default_scheme="http",
            endpoint_default_port=11434,
        ),
        PROVIDER_OLLAMA_CLOUD: ProviderProfile(
            provider_id=PROVIDER_OLLAMA_CLOUD,
            backend_kind=BackendKind.OLLAMA,
            network_boundary=NetworkBoundary.EXTERNAL_CLOUD,
            raw_pii_policy=PiiPolicy.DENY,
            sanitized_pii_policy=PiiPolicy.ALLOW,
            supports_structured_json=True,
            supports_text=True,
            supports_multimodal=False,
            health_probe_kind=HealthProbeKind.OLLAMA_TAGS,
            cost_class=CostClass.MEDIUM,
            latency_class=LatencyClass.MEDIUM,
            priority_hint=30,
            endpoint_env_keys=("OLLAMA_HOST", "OLLAMA_BASE_URL"),
            credential_env_keys=("OLLAMA_API_KEY",),
            default_model_env="OLLAMA_MODEL",
            historical_names=("ollama_cloud",),
            api_key_optional=False,
            endpoint_default_scheme="https",
            endpoint_default_port=None,
        ),
        PROVIDER_GPU_OLLAMA: ProviderProfile(
            provider_id=PROVIDER_GPU_OLLAMA,
            backend_kind=BackendKind.OLLAMA,
            # Current runtime reaches this endpoint over a private overlay, but no
            # accepted trust-boundary decision was found. RAW remains fail-closed.
            network_boundary=NetworkBoundary.UNKNOWN_BOUNDARY,
            raw_pii_policy=PiiPolicy.DENY,
            sanitized_pii_policy=PiiPolicy.ALLOW,
            supports_structured_json=True,
            supports_text=True,
            supports_multimodal=False,
            health_probe_kind=HealthProbeKind.OLLAMA_TAGS,
            cost_class=CostClass.FREE_LOCAL,
            latency_class=LatencyClass.LOW,
            priority_hint=20,
            endpoint_env_keys=(
                "LOCAL_GPU_OLLAMA_HOST",
                "LOCAL_GPU_OLLAMA_BASE_URL",
                "LOCAL_GPU_OLLAMA_URL",
            ),
            credential_env_keys=("LOCAL_GPU_OLLAMA_API_KEY",),
            default_model_env="LOCAL_GPU_OLLAMA_MODEL",
            historical_names=(
                "local_gpu_ollama",
                "local_gpu_vision",
                "gpu-ollama",
                "100.91.166.5:11434",
            ),
            api_key_optional=True,
            endpoint_default_scheme="http",
            endpoint_default_port=11434,
        ),
        PROVIDER_GPU_WHISPER: ProviderProfile(
            provider_id=PROVIDER_GPU_WHISPER,
            backend_kind=BackendKind.FASTER_WHISPER_HTTP,
            network_boundary=NetworkBoundary.UNKNOWN_BOUNDARY,
            raw_pii_policy=PiiPolicy.DENY,
            sanitized_pii_policy=PiiPolicy.ALLOW,
            supports_structured_json=False,
            supports_text=False,
            supports_multimodal=False,
            health_probe_kind=HealthProbeKind.NONE,
            cost_class=CostClass.FREE_LOCAL,
            latency_class=LatencyClass.LOW,
            priority_hint=20,
            endpoint_env_keys=("LOCAL_GPU_WHISPER_BASE_URL", "LOCAL_GPU_WHISPER_URL"),
            credential_env_keys=("LOCAL_GPU_WHISPER_API_KEY", "AI_API_KEY"),
            default_model_env="LOCAL_GPU_WHISPER_MODEL",
            historical_names=("local_gpu_whisper",),
            api_key_optional=True,
            endpoint_default_scheme="http",
            endpoint_default_port=8092,
        ),
        PROVIDER_MISTRAL_EXTERNAL: ProviderProfile(
            provider_id=PROVIDER_MISTRAL_EXTERNAL,
            backend_kind=BackendKind.MISTRAL,
            network_boundary=NetworkBoundary.EXTERNAL_CLOUD,
            raw_pii_policy=PiiPolicy.DENY,
            sanitized_pii_policy=PiiPolicy.ALLOW,
            supports_structured_json=True,
            supports_text=True,
            supports_multimodal=False,
            health_probe_kind=HealthProbeKind.NONE,
            cost_class=CostClass.MEDIUM,
            latency_class=LatencyClass.MEDIUM,
            priority_hint=40,
            endpoint_env_keys=("MISTRAL_API_BASE", "MISTRAL_ENDPOINT"),
            credential_env_keys=("MISTRAL_API_KEY", "AI_API_KEY"),
            default_model_env="MISTRAL_MODEL",
            historical_names=("mistral", "mistral_ocr"),
            api_key_optional=False,
            endpoint_default_scheme="https",
            endpoint_default_port=None,
        ),
        PROVIDER_OPENAI_EXTERNAL: ProviderProfile(
            provider_id=PROVIDER_OPENAI_EXTERNAL,
            backend_kind=BackendKind.OPENAI_COMPATIBLE,
            network_boundary=NetworkBoundary.EXTERNAL_CLOUD,
            raw_pii_policy=PiiPolicy.DENY,
            sanitized_pii_policy=PiiPolicy.ALLOW,
            supports_structured_json=True,
            supports_text=True,
            supports_multimodal=False,
            health_probe_kind=HealthProbeKind.NONE,
            cost_class=CostClass.UNKNOWN,
            latency_class=LatencyClass.UNKNOWN,
            priority_hint=50,
            endpoint_env_keys=("OPENAI_BASE_URL",),
            credential_env_keys=("OPENAI_API_KEY", "AI_API_KEY"),
            default_model_env="OPENAI_MODEL",
            historical_names=("openai",),
            api_key_optional=False,
            endpoint_default_scheme="https",
            endpoint_default_port=None,
        ),
        PROVIDER_DEEPSEEK_EXTERNAL: ProviderProfile(
            provider_id=PROVIDER_DEEPSEEK_EXTERNAL,
            backend_kind=BackendKind.OPENAI_COMPATIBLE,
            network_boundary=NetworkBoundary.EXTERNAL_CLOUD,
            raw_pii_policy=PiiPolicy.DENY,
            sanitized_pii_policy=PiiPolicy.ALLOW,
            supports_structured_json=True,
            supports_text=True,
            supports_multimodal=False,
            health_probe_kind=HealthProbeKind.NONE,
            cost_class=CostClass.UNKNOWN,
            latency_class=LatencyClass.UNKNOWN,
            priority_hint=45,
            endpoint_env_keys=("DEEPSEEK_BASE_URL",),
            credential_env_keys=("DEEPSEEK_API_KEY", "AI_API_KEY"),
            default_model_env="DEEPSEEK_MODEL",
            historical_names=("deepseek",),
            api_key_optional=False,
            endpoint_default_scheme="https",
            endpoint_default_port=None,
        ),
    }


_CATALOG: dict[str, ProviderProfile] = _build_catalog()


def get_provider_catalog() -> dict[str, ProviderProfile]:
    """Return a shallow copy of the canonical catalog."""

    return dict(_CATALOG)


def get_provider_profile(provider_id: str) -> ProviderProfile:
    """Return one provider profile; unknown ids fail closed."""

    if provider_id not in _CATALOG:
        raise KeyError(f"Unknown provider_id: {provider_id}")
    return _CATALOG[provider_id]
