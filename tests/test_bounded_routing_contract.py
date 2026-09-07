import pytest

from ai_core.budget import AttemptBudget
from ai_core.capabilities import ProviderCapability
from ai_core.errors import (
    AiErrorKind,
    NoEligibleProviderError,
    RawRouteExhaustedError,
    RequestDeadlineExceededError,
    classify_provider_error,
)
from ai_core.health import ProviderHealthStatus, ProviderHealthStore
from ai_core.privacy import DataClass, OutboundForm
from ai_core.routing import PrivacyAwareRouter, RejectionReason, RouteCandidate


GPU_JSON = RouteCandidate("gpu_ollama", "qwen3.5:9b")
MISTRAL_JSON = RouteCandidate("mistral_external", "ministral-8b-2512")


class StatusError(RuntimeError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"status={status_code}")


class ConnectError(RuntimeError):
    pass


def test_error_taxonomy_keeps_retry_narrow_and_fallback_broader():
    timeout = classify_provider_error(TimeoutError("slow"))
    assert timeout.kind == AiErrorKind.TIMEOUT
    assert timeout.retryable_same_provider is True
    assert timeout.fallback_eligible is True
    assert timeout.terminal is False

    rate_limit = classify_provider_error(StatusError(429))
    assert rate_limit.kind == AiErrorKind.RATE_LIMIT
    assert rate_limit.retryable_same_provider is True
    assert rate_limit.fallback_eligible is True

    server = classify_provider_error(StatusError(503))
    assert server.kind == AiErrorKind.SERVER
    assert server.retryable_same_provider is False
    assert server.fallback_eligible is True

    auth = classify_provider_error(StatusError(401))
    assert auth.kind == AiErrorKind.AUTH
    assert auth.retryable_same_provider is False
    assert auth.fallback_eligible is False
    assert auth.terminal is True

    connect = classify_provider_error(ConnectError("down"))
    assert connect.kind == AiErrorKind.TRANSPORT
    assert connect.retryable_same_provider is False
    assert connect.fallback_eligible is True


def test_health_state_is_isolated_by_provider_and_model():
    store = ProviderHealthStore()
    assert store.is_healthy("gpu_ollama", model="qwen3.5:9b")
    assert store.is_healthy("ollama_cloud")

    store.set_status("ollama_cloud", ProviderHealthStatus.QUOTA_LIMITED)
    assert not store.is_healthy("ollama_cloud")
    assert store.is_healthy("gpu_ollama", model="qwen3.5:9b")

    store.set_status(
        "gpu_ollama",
        ProviderHealthStatus.MODEL_MISSING,
        model="qwen2.5vl:7b",
    )
    assert not store.is_healthy("gpu_ollama", model="qwen2.5vl:7b")
    assert store.is_healthy("gpu_ollama", model="qwen3.5:9b")

    store.set_status("gpu_ollama", ProviderHealthStatus.UNREACHABLE)
    assert not store.is_healthy("gpu_ollama", model="qwen3.5:9b")


def test_sanitized_private_route_is_deterministic_by_provider_priority():
    router = PrivacyAwareRouter()
    plan = router.plan(
        [MISTRAL_JSON, GPU_JSON],
        capability=ProviderCapability.STRUCTURED_JSON,
        data_class=DataClass.PRIVATE_CLIENT_DATA,
        outbound_form=OutboundForm.SANITIZED,
        require_nonempty=True,
    )
    assert plan.eligible == (GPU_JSON, MISTRAL_JSON)
    assert plan.winner == GPU_JSON


def test_unhealthy_candidate_is_skipped_without_poisoning_other_provider():
    store = ProviderHealthStore()
    store.set_status(
        "gpu_ollama",
        ProviderHealthStatus.QUOTA_LIMITED,
        model="qwen3.5:9b",
    )
    router = PrivacyAwareRouter(health_store=store)
    plan = router.plan(
        [GPU_JSON, MISTRAL_JSON],
        capability=ProviderCapability.STRUCTURED_JSON,
        data_class=DataClass.PRIVATE_CLIENT_DATA,
        outbound_form=OutboundForm.SANITIZED,
        require_nonempty=True,
    )
    assert plan.eligible == (MISTRAL_JSON,)
    assert plan.rejected[0].candidate == GPU_JSON
    assert plan.rejected[0].reason == RejectionReason.UNHEALTHY


def test_authorized_provider_whitelist_is_enforced():
    router = PrivacyAwareRouter(authorized_provider_ids=("mistral_external",))
    plan = router.plan(
        [GPU_JSON, MISTRAL_JSON],
        capability=ProviderCapability.STRUCTURED_JSON,
        data_class=DataClass.PUBLIC_NO_PII,
        outbound_form=OutboundForm.SANITIZED,
        require_nonempty=True,
    )
    assert plan.eligible == (MISTRAL_JSON,)
    assert any(
        rejection.candidate == GPU_JSON
        and rejection.reason == RejectionReason.UNAUTHORIZED_PROVIDER
        for rejection in plan.rejected
    )


def test_sensitive_raw_never_falls_through_to_gpu_or_external_cloud():
    router = PrivacyAwareRouter()
    with pytest.raises(RawRouteExhaustedError) as exc_info:
        router.plan(
            [GPU_JSON, MISTRAL_JSON],
            capability=ProviderCapability.STRUCTURED_JSON,
            data_class=DataClass.PRIVATE_CLIENT_DATA,
            outbound_form=OutboundForm.RAW,
            require_nonempty=True,
        )
    assert "NEW" in str(exc_info.value)
    assert "SANITIZED" in str(exc_info.value)


def test_unknown_capability_profile_fails_closed():
    unknown_model = RouteCandidate("gpu_ollama", "unknown-model")
    router = PrivacyAwareRouter()
    with pytest.raises(NoEligibleProviderError):
        router.plan(
            [unknown_model],
            capability=ProviderCapability.VISION_IMAGE,
            data_class=DataClass.PUBLIC_NO_PII,
            outbound_form=OutboundForm.SANITIZED,
            require_nonempty=True,
        )


def test_shared_deadline_reserves_time_for_future_fallback():
    budget = AttemptBudget.from_timeout(
        now_monotonic=1000.0,
        total_timeout_seconds=120.0,
        min_attempt_seconds=0.1,
    )

    first = budget.timeout_for_attempt(
        now_monotonic=1000.0,
        configured_timeout_seconds=120.0,
        future_attempts=1,
        reserve_per_future_attempt_seconds=30.0,
    )
    assert first == 90.0

    second = budget.timeout_for_attempt(
        now_monotonic=1095.0,
        configured_timeout_seconds=60.0,
        future_attempts=0,
    )
    assert second == 25.0

    with pytest.raises(RequestDeadlineExceededError):
        budget.timeout_for_attempt(
            now_monotonic=1120.0,
            configured_timeout_seconds=1.0,
        )


def test_attempt_budget_rejects_invalid_configuration():
    with pytest.raises(ValueError):
        AttemptBudget.from_timeout(now_monotonic=0.0, total_timeout_seconds=0.0)

    budget = AttemptBudget.from_timeout(now_monotonic=0.0, total_timeout_seconds=10.0)
    with pytest.raises(ValueError):
        budget.timeout_for_attempt(
            now_monotonic=0.0,
            configured_timeout_seconds=5.0,
            future_attempts=-1,
        )
