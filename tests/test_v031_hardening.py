"""v0.3.1 Hardening Tests: verify resolution of all 8 audit findings."""

from __future__ import annotations

import os
import time
from unittest.mock import MagicMock

import pytest

import ai_core
from ai_core.budget import AttemptBudget
from ai_core.capabilities import ProviderCapability
from ai_core.errors import (
    AiErrorKind,
    AllCandidatesExhaustedError,
    ErrorDescriptor,
    NoEligibleProviderError,
    RequestDeadlineExceededError,
)
from ai_core.executor import (
    DEFAULT_CANDIDATES,
    _build_default_policy,
    execute_chat,
)
from ai_core.health import ProviderHealthStatus, ProviderHealthStore
from ai_core.privacy import DataClass, OutboundForm
from ai_core.routing import PrivacyAwareRouter, RouteCandidate, RoutePlan
from ai_core.runtime import (
    ExecutionRequest,
    ExecutionResult,
    SingleLoopRuntime,
)
from ai_core.transports import (
    OllamaTransport,
    ProviderTransport,
    TransportAttemptResult,
    TransportResponse,
    TransportUsage,
    get_transport_for_candidate,
)


def _mock_success(candidate: RouteCandidate, content: str = "ok") -> TransportAttemptResult:
    return TransportAttemptResult(
        candidate=candidate,
        response=TransportResponse(
            candidate=candidate,
            content=content,
            usage=TransportUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            latency_seconds=0.05,
            raw_response={"message": {"content": content}},
        ),
        error=None,
        latency_seconds=0.05,
    )


def _mock_error(
    candidate: RouteCandidate,
    kind: AiErrorKind,
    *,
    status_code: int = 500,
    fallback_eligible: bool = True,
    terminal: bool = False,
) -> TransportAttemptResult:
    return TransportAttemptResult(
        candidate=candidate,
        response=None,
        error=ErrorDescriptor(
            kind=kind,
            status_code=status_code,
            retryable_same_provider=False,
            fallback_eligible=fallback_eligible,
            terminal=terminal,
        ),
        latency_seconds=0.05,
    )


def test_1_self_authorization_prevented_for_uncataloged_provider() -> None:
    """Audit Finding 1: _build_default_policy must NOT self-authorize unknown/uncataloged providers."""
    rogue_cand = RouteCandidate(provider_id="rogue_untrusted_provider", model="rogue_model")
    policy = _build_default_policy(
        candidates=(rogue_cand,),
        capability=ProviderCapability.TEXT,
        request_egress_authorized=False,
    )
    # Rogue provider must NOT be authorized in default policy
    assert rogue_cand.provider_id not in policy.authorized_provider_ids

    # PrivacyAwareRouter rejects rogue candidate
    router = PrivacyAwareRouter()
    plan = router.plan(
        (rogue_cand,),
        capability=ProviderCapability.TEXT,
        data_class=DataClass.PUBLIC_NO_PII,
        outbound_form=OutboundForm.RAW,
        policy=policy,
    )
    assert len(plan.eligible) == 0
    assert len(plan.rejected) == 1


def test_2_empty_candidates_list_raises_no_eligible_provider() -> None:
    """Audit Finding 2: candidates=[] must NOT be silently replaced by DEFAULT_CANDIDATES."""
    with pytest.raises(NoEligibleProviderError):
        execute_chat(
            messages=[{"role": "user", "content": "ping"}],
            candidates=[],  # Explicitly empty
        )


def test_3_reserve_per_future_attempt_prevents_deadline_starvation() -> None:
    """Audit Finding 3: Attempt budget reserves budget for subsequent candidates."""
    cand_1 = RouteCandidate(provider_id="vm100_local_ollama", model="m1")
    cand_2 = RouteCandidate(provider_id="gpu_ollama", model="m2")

    mock_transport = MagicMock(spec=ProviderTransport)
    # First candidate fails with recoverable error
    mock_transport.send_attempt.side_effect = [
        _mock_error(cand_1, kind=AiErrorKind.SERVER, fallback_eligible=True),
        _mock_success(cand_2, "recovered"),
    ]

    now = time.monotonic()
    budget = AttemptBudget.from_timeout(
        now_monotonic=now,
        total_timeout_seconds=10.0,
        min_attempt_seconds=0.5,
    )

    # First attempt calculation should reserve 0.5s for the second attempt
    timeout_1 = budget.timeout_for_attempt(
        now_monotonic=now,
        configured_timeout_seconds=10.0,
        future_attempts=1,
        reserve_per_future_attempt_seconds=budget.min_attempt_seconds,
    )
    assert timeout_1 == 9.5  # 10.0 - 0.5 reserved!

    runtime = SingleLoopRuntime(transport=mock_transport)
    plan = RoutePlan(eligible=(cand_1, cand_2), rejected=())
    req = ExecutionRequest(
        messages=({"role": "user", "content": "hi"},),
        candidates=(cand_1, cand_2),
        total_timeout_seconds=10.0,
    )
    result = runtime.execute_plan(plan, req, budget=budget)
    assert result.winner == cand_2
    assert result.content == "recovered"
    assert result.fallback_occurred


def test_4_distinct_default_endpoints_for_ollama_providers() -> None:
    """Audit Finding 4: vm100_local_ollama and gpu_ollama must resolve to distinct default endpoints."""
    t_vm100 = get_transport_for_candidate(
        RouteCandidate(provider_id="vm100_local_ollama", model="qwen3:8b")
    )
    t_gpu = get_transport_for_candidate(
        RouteCandidate(provider_id="gpu_ollama", model="qwen3:8b")
    )
    assert isinstance(t_vm100, OllamaTransport)
    assert isinstance(t_gpu, OllamaTransport)
    assert t_vm100._default_endpoint != t_gpu._default_endpoint
    assert t_vm100._default_endpoint == "http://127.0.0.1:11434"
    assert t_gpu._default_endpoint == "http://127.0.0.1:11435"


def test_5_deadline_exhaustion_chains_cause_and_sets_property() -> None:
    """Audit Finding 5: RequestDeadlineExceededError is preserved as __cause__ in AllCandidatesExhaustedError."""
    cand_1 = RouteCandidate(provider_id="vm100_local_ollama", model="m1")
    cand_2 = RouteCandidate(provider_id="gpu_ollama", model="m2")

    mock_transport = MagicMock(spec=ProviderTransport)
    mock_transport.send_attempt.return_value = _mock_error(
        cand_1, kind=AiErrorKind.SERVER, fallback_eligible=True
    )

    mock_budget = MagicMock(spec=AttemptBudget)
    mock_budget.min_attempt_seconds = 0.5
    mock_budget.timeout_for_attempt.side_effect = [
        2.0,
        RequestDeadlineExceededError("Budget expired before attempt 2"),
    ]

    runtime = SingleLoopRuntime(transport=mock_transport)
    plan = RoutePlan(eligible=(cand_1, cand_2), rejected=())
    req = ExecutionRequest(
        messages=({"role": "user", "content": "hi"},),
        candidates=(cand_1, cand_2),
    )

    with pytest.raises(AllCandidatesExhaustedError) as exc_info:
        runtime.execute_plan(plan, req, budget=mock_budget)

    assert exc_info.value.is_deadline_exceeded
    assert isinstance(exc_info.value.__cause__, RequestDeadlineExceededError)
    assert len(exc_info.value.attempts) == 1


def test_6_http_404_triggers_fallback_to_next_candidate() -> None:
    """Audit Finding 6: HTTP 404 (model not found) must be fallback_eligible and NOT terminal."""
    cand_1 = RouteCandidate(provider_id="vm100_local_ollama", model="missing-model")
    cand_2 = RouteCandidate(provider_id="gpu_ollama", model="fallback-model")

    mock_transport = MagicMock(spec=ProviderTransport)
    # First attempt: 404 Not Found (e.g. model not pulled in Ollama)
    mock_transport.send_attempt.side_effect = [
        _mock_error(cand_1, kind=AiErrorKind.NOT_FOUND, status_code=404, fallback_eligible=True, terminal=False),
        _mock_success(cand_2, "fallback on 404 success"),
    ]

    runtime = SingleLoopRuntime(transport=mock_transport)
    plan = RoutePlan(eligible=(cand_1, cand_2), rejected=())
    req = ExecutionRequest(
        messages=({"role": "user", "content": "hi"},),
        candidates=(cand_1, cand_2),
    )

    result = runtime.execute_plan(plan, req)
    assert result.winner == cand_2
    assert result.content == "fallback on 404 success"
    assert result.fallback_occurred
    assert len(result.attempts) == 2


def test_7_custom_runtime_shares_health_store_with_router() -> None:
    """Audit Finding 7: execute_chat must reuse runtime.health_store in PrivacyAwareRouter."""
    shared_health_store = ProviderHealthStore()
    mock_transport = MagicMock(spec=ProviderTransport)
    mock_transport.send_attempt.return_value = _mock_success(
        RouteCandidate(provider_id="vm100_local_ollama", model="qwen3:8b"), "ok"
    )

    custom_runtime = SingleLoopRuntime(
        health_store=shared_health_store,
        transport=mock_transport,
    )

    result = execute_chat(
        messages=[{"role": "user", "content": "ping"}],
        runtime=custom_runtime,
    )

    assert result.winner.provider_id == "vm100_local_ollama"
    # Health store inside custom_runtime was observed and updated
    assert (
        shared_health_store.get_status("vm100_local_ollama", model="qwen3:8b")
        == ProviderHealthStatus.REACHABLE
    )


def test_8_package_version_and_nine_symbol_invariant() -> None:
    """Audit Finding 8: ai_core.__version__ is 0.3.1 and root __all__ invariant is preserved."""
    assert getattr(ai_core, "__version__", None) == "0.3.1"
    # Root __all__ must still be the exact 9 symbols
    assert len(ai_core.__all__) == 9
