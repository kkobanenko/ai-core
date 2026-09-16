import pytest

from ai_core.errors import AiErrorKind, NoEligibleProviderError, classify_provider_error
from ai_core.budget import AttemptBudget
from ai_core.capabilities import (
    CapabilityEvidence,
    CapabilityEvidenceLevel,
    ProviderCapability,
)
from ai_core.health import ProviderHealthStatus, ProviderHealthStore
from ai_core.privacy import DataClass, OutboundForm
from ai_core.provider_catalog import NetworkBoundary
from ai_core.routing import (
    CapabilityAuthorization,
    PrivacyAwareRouter,
    RejectionReason,
    RouteCandidate,
    RoutePolicy,
)


GPU_JSON = RouteCandidate("gpu_ollama", "qwen3.5:9b")
MISTRAL_JSON = RouteCandidate("mistral_external", "ministral-8b-2512")
LOCAL_JSON = RouteCandidate("vm100_local_ollama", "qwen3.5:9b")


def auth(candidate: RouteCandidate, capability: ProviderCapability):
    return CapabilityAuthorization(
        provider_id=candidate.provider_id,
        model=candidate.model,
        capability=capability,
    )


def policy_for(
    *candidates: RouteCandidate,
    capability: ProviderCapability = ProviderCapability.STRUCTURED_JSON,
    request_egress_authorized: object = True,
) -> RoutePolicy:
    return RoutePolicy(
        authorized_provider_ids=frozenset(
            candidate.provider_id for candidate in candidates
        ),
        capability_authorizations=frozenset(
            auth(candidate, capability) for candidate in candidates
        ),
        request_egress_authorized=request_egress_authorized,
    )


class StatusError(RuntimeError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"status={status_code}")


class ConnectError(RuntimeError):
    pass


def test_authorized_candidates_preserve_caller_order():
    router = PrivacyAwareRouter()

    plan = router.plan(
        [MISTRAL_JSON, GPU_JSON],
        capability=ProviderCapability.STRUCTURED_JSON,
        data_class=DataClass.PRIVATE_CLIENT_DATA,
        outbound_form=OutboundForm.SANITIZED,
        policy=policy_for(MISTRAL_JSON, GPU_JSON),
        require_nonempty=True,
    )

    assert plan.eligible == (MISTRAL_JSON, GPU_JSON)
    assert plan.winner == MISTRAL_JSON


def test_unknown_provider_fails_closed():
    unknown = RouteCandidate("unknown_provider", "model")
    router = PrivacyAwareRouter()

    plan = router.plan(
        [unknown],
        capability=ProviderCapability.TEXT,
        data_class=DataClass.PUBLIC_NO_PII,
        outbound_form=OutboundForm.RAW,
        policy=RoutePolicy(
            authorized_provider_ids=frozenset({"unknown_provider"}),
            capability_authorizations=frozenset(
                {
                    CapabilityAuthorization(
                        "unknown_provider",
                        "model",
                        ProviderCapability.TEXT,
                    )
                }
            ),
        ),
    )

    assert plan.eligible == ()
    assert plan.rejected[0].reason is RejectionReason.UNKNOWN_PROVIDER


def test_provider_authorization_is_explicit():
    router = PrivacyAwareRouter()

    plan = router.plan(
        [GPU_JSON],
        capability=ProviderCapability.STRUCTURED_JSON,
        data_class=DataClass.PUBLIC_NO_PII,
        outbound_form=OutboundForm.SANITIZED,
        policy=RoutePolicy(
            authorized_provider_ids=frozenset(),
            capability_authorizations=frozenset(
                {auth(GPU_JSON, ProviderCapability.STRUCTURED_JSON)}
            ),
            request_egress_authorized=True,
        ),
    )

    assert plan.eligible == ()
    assert plan.rejected[0].reason is RejectionReason.UNAUTHORIZED_PROVIDER


def test_capability_authorization_is_exact_and_explicit():
    router = PrivacyAwareRouter()

    plan = router.plan(
        [GPU_JSON],
        capability=ProviderCapability.STRUCTURED_JSON,
        data_class=DataClass.PUBLIC_NO_PII,
        outbound_form=OutboundForm.SANITIZED,
        policy=RoutePolicy(
            authorized_provider_ids=frozenset({"gpu_ollama"}),
            capability_authorizations=frozenset(),
            request_egress_authorized=True,
        ),
    )

    assert plan.eligible == ()
    assert plan.rejected[0].reason is RejectionReason.CAPABILITY_NOT_AUTHORIZED


def test_runtime_capability_evidence_alone_never_authorizes_route():
    evidence = CapabilityEvidence(
        provider_id="gpu_ollama",
        model="qwen3.5:9b",
        capability=ProviderCapability.STRUCTURED_JSON,
        network_boundary=NetworkBoundary.UNKNOWN_BOUNDARY,
        level=CapabilityEvidenceLevel.RUNTIME_OBSERVED,
    )
    assert evidence.level is CapabilityEvidenceLevel.RUNTIME_OBSERVED

    router = PrivacyAwareRouter()
    plan = router.plan(
        [GPU_JSON],
        capability=ProviderCapability.STRUCTURED_JSON,
        data_class=DataClass.PUBLIC_NO_PII,
        outbound_form=OutboundForm.SANITIZED,
        policy=RoutePolicy(
            authorized_provider_ids=frozenset({"gpu_ollama"}),
            capability_authorizations=frozenset(),
            request_egress_authorized=True,
        ),
    )

    assert plan.eligible == ()
    assert plan.rejected[0].reason is RejectionReason.CAPABILITY_NOT_AUTHORIZED


@pytest.mark.parametrize(
    "candidate,egress_authorized",
    [
        (LOCAL_JSON, False),
        (MISTRAL_JSON, True),
        (GPU_JSON, True),
    ],
)
def test_secret_is_always_rejected(candidate, egress_authorized):
    router = PrivacyAwareRouter()

    plan = router.plan(
        [candidate],
        capability=ProviderCapability.STRUCTURED_JSON,
        data_class=DataClass.SECRET,
        outbound_form=OutboundForm.SURROGATED,
        policy=policy_for(
            candidate,
            request_egress_authorized=egress_authorized,
        ),
    )

    assert plan.eligible == ()
    assert plan.rejected[0].reason is RejectionReason.PRIVACY_EGRESS_DENIED


@pytest.mark.parametrize(
    "authorization",
    [False, 1, "yes", object()],
)
def test_nonlocal_egress_requires_literal_true(authorization):
    router = PrivacyAwareRouter()

    plan = router.plan(
        [GPU_JSON],
        capability=ProviderCapability.STRUCTURED_JSON,
        data_class=DataClass.PUBLIC_NO_PII,
        outbound_form=OutboundForm.RAW,
        policy=policy_for(
            GPU_JSON,
            request_egress_authorized=authorization,
        ),
    )

    assert plan.eligible == ()
    assert plan.rejected[0].reason is RejectionReason.PRIVACY_EGRESS_DENIED


def test_explicit_nonlocal_egress_authorization_allows_route():
    router = PrivacyAwareRouter()

    plan = router.plan(
        [GPU_JSON],
        capability=ProviderCapability.STRUCTURED_JSON,
        data_class=DataClass.PUBLIC_NO_PII,
        outbound_form=OutboundForm.RAW,
        policy=policy_for(
            GPU_JSON,
            request_egress_authorized=True,
        ),
        require_nonempty=True,
    )

    assert plan.eligible == (GPU_JSON,)


def test_negative_health_only_removes_candidate():
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
        data_class=DataClass.PUBLIC_NO_PII,
        outbound_form=OutboundForm.SANITIZED,
        policy=policy_for(GPU_JSON, MISTRAL_JSON),
        require_nonempty=True,
    )

    assert plan.eligible == (MISTRAL_JSON,)
    assert plan.rejected[0].candidate == GPU_JSON
    assert plan.rejected[0].reason is RejectionReason.HEALTH_BLOCKED


def test_unknown_health_does_not_create_authorization():
    store = ProviderHealthStore()

    assert not store.blocks_route(
        "gpu_ollama",
        model="qwen3.5:9b",
    )

    router = PrivacyAwareRouter(health_store=store)

    plan = router.plan(
        [GPU_JSON],
        capability=ProviderCapability.STRUCTURED_JSON,
        data_class=DataClass.PUBLIC_NO_PII,
        outbound_form=OutboundForm.SANITIZED,
        policy=RoutePolicy(
            authorized_provider_ids=frozenset(),
            capability_authorizations=frozenset(),
            request_egress_authorized=True,
        ),
    )

    assert plan.eligible == ()
    assert plan.rejected[0].reason is RejectionReason.UNAUTHORIZED_PROVIDER


def test_provider_level_health_block_applies_to_every_model():
    store = ProviderHealthStore()
    store.set_status(
        "gpu_ollama",
        ProviderHealthStatus.UNREACHABLE,
    )

    assert store.blocks_route(
        "gpu_ollama",
        model="qwen3.5:9b",
    )
    assert store.blocks_route(
        "gpu_ollama",
        model="another-model",
    )


def test_empty_required_plan_raises_generic_error_only():
    router = PrivacyAwareRouter()

    with pytest.raises(NoEligibleProviderError):
        router.plan(
            [GPU_JSON],
            capability=ProviderCapability.STRUCTURED_JSON,
            data_class=DataClass.PUBLIC_NO_PII,
            outbound_form=OutboundForm.SANITIZED,
            policy=RoutePolicy(
                authorized_provider_ids=frozenset(),
                capability_authorizations=frozenset(),
                request_egress_authorized=True,
            ),
            require_nonempty=True,
        )


def test_error_taxonomy_keeps_retry_narrow_and_fallback_broader():
    timeout = classify_provider_error(TimeoutError("slow"))
    assert timeout.kind is AiErrorKind.TIMEOUT
    assert timeout.retryable_same_provider is True
    assert timeout.fallback_eligible is True
    assert timeout.terminal is False

    rate_limit = classify_provider_error(StatusError(429))
    assert rate_limit.kind is AiErrorKind.RATE_LIMIT
    assert rate_limit.retryable_same_provider is True
    assert rate_limit.fallback_eligible is True

    server = classify_provider_error(StatusError(503))
    assert server.kind is AiErrorKind.SERVER
    assert server.retryable_same_provider is False
    assert server.fallback_eligible is True

    auth_error = classify_provider_error(StatusError(401))
    assert auth_error.kind is AiErrorKind.AUTH
    assert auth_error.retryable_same_provider is False
    assert auth_error.fallback_eligible is False
    assert auth_error.terminal is True

    connection = classify_provider_error(ConnectError("down"))
    assert connection.kind is AiErrorKind.TRANSPORT
    assert connection.retryable_same_provider is False
    assert connection.fallback_eligible is True


def test_no_historical_raw_route_exhausted_error_contract():
    import ai_core.errors as errors

    assert not hasattr(errors, "RawRouteExhaustedError")


def test_shared_deadline_budget_is_pure_and_reserves_future_time():
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
    assert budget.remaining_seconds(now_monotonic=1095.0) == 25.0


def test_attempt_budget_rejects_invalid_configuration():
    with pytest.raises(ValueError):
        AttemptBudget.from_timeout(
            now_monotonic=0.0,
            total_timeout_seconds=0.0,
        )

    budget = AttemptBudget.from_timeout(
        now_monotonic=0.0,
        total_timeout_seconds=10.0,
    )

    with pytest.raises(ValueError):
        budget.timeout_for_attempt(
            now_monotonic=0.0,
            configured_timeout_seconds=5.0,
            future_attempts=-1,
        )
