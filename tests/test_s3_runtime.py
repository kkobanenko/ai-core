"""S3 Runtime Tests: verify single-loop execution, fallback, budget enforcement, and telemetry."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from ai_core.budget import AttemptBudget
from ai_core.capabilities import ProviderCapability
from ai_core.errors import (
    AiErrorKind,
    AllCandidatesExhaustedError,
    ErrorDescriptor,
    NoEligibleProviderError,
    RequestDeadlineExceededError,
)
from ai_core.health import ProviderHealthStatus, ProviderHealthStore
from ai_core.routing import RouteCandidate, RoutePlan
from ai_core.runtime import ExecutionRequest, ExecutionResult, SingleLoopRuntime
from ai_core.transports import (
    ProviderTransport,
    TransportAttemptResult,
    TransportResponse,
    TransportUsage,
)

CANDIDATE_1 = RouteCandidate(provider_id="vm100_local_ollama", model="qwen3:8b")
CANDIDATE_2 = RouteCandidate(provider_id="gpu_ollama", model="qwen3:8b")
CANDIDATE_3 = RouteCandidate(provider_id="mistral_external", model="mistral-small-latest")


def _make_request(
    candidates: tuple[RouteCandidate, ...] = (CANDIDATE_1, CANDIDATE_2),
    total_timeout_seconds: float = 30.0,
    request_egress_authorized: bool = True,
) -> ExecutionRequest:
    return ExecutionRequest(
        messages=({"role": "user", "content": "test prompt"},),
        candidates=candidates,
        capability=ProviderCapability.TEXT,
        total_timeout_seconds=total_timeout_seconds,
        request_egress_authorized=request_egress_authorized,
    )


def _mock_success(candidate: RouteCandidate, content: str = "success") -> TransportAttemptResult:
    return TransportAttemptResult(
        candidate=candidate,
        response=TransportResponse(
            candidate=candidate,
            content=content,
            usage=TransportUsage(prompt_tokens=5, completion_tokens=10, total_tokens=15),
            latency_seconds=0.2,
            raw_response={"content": content},
        ),
        error=None,
        latency_seconds=0.2,
    )


def _mock_error(
    candidate: RouteCandidate,
    kind: AiErrorKind = AiErrorKind.TIMEOUT,
    fallback_eligible: bool = True,
) -> TransportAttemptResult:
    return TransportAttemptResult(
        candidate=candidate,
        response=None,
        error=ErrorDescriptor(
            kind=kind,
            status_code=504 if kind == AiErrorKind.TIMEOUT else 500,
            retryable_same_provider=True,
            fallback_eligible=fallback_eligible,
            terminal=not fallback_eligible,
        ),
        latency_seconds=1.0,
    )


class TestSingleLoopRuntime:
    """Test suite for SingleLoopRuntime execution logic."""

    def test_empty_eligible_candidates_raises_no_eligible_provider(self) -> None:
        runtime = SingleLoopRuntime()
        plan = RoutePlan(eligible=(), rejected=())
        request = _make_request()

        with pytest.raises(NoEligibleProviderError, match="No candidate survived"):
            runtime.execute_plan(plan, request)

    def test_single_candidate_success(self) -> None:
        mock_transport = MagicMock(spec=ProviderTransport)
        mock_transport.send_attempt.return_value = _mock_success(CANDIDATE_1, "hello world")

        health_store = ProviderHealthStore()
        runtime = SingleLoopRuntime(health_store=health_store, transport=mock_transport)
        plan = RoutePlan(eligible=(CANDIDATE_1,), rejected=())
        request = _make_request(candidates=(CANDIDATE_1,))

        result = runtime.execute_plan(plan, request)

        assert isinstance(result, ExecutionResult)
        assert result.winner == CANDIDATE_1
        assert result.content == "hello world"
        assert not result.fallback_occurred
        assert len(result.attempts) == 1
        assert result.attempts[0].ok
        assert health_store.get_status("vm100_local_ollama", model="qwen3:8b") == ProviderHealthStatus.REACHABLE

    def test_fallback_to_second_candidate_on_recoverable_error(self) -> None:
        mock_transport = MagicMock(spec=ProviderTransport)
        # First attempt fails with TIMEOUT (fallback_eligible=True), second succeeds
        mock_transport.send_attempt.side_effect = [
            _mock_error(CANDIDATE_1, kind=AiErrorKind.TIMEOUT, fallback_eligible=True),
            _mock_success(CANDIDATE_2, "fallback response"),
        ]

        health_store = ProviderHealthStore()
        runtime = SingleLoopRuntime(health_store=health_store, transport=mock_transport)
        plan = RoutePlan(eligible=(CANDIDATE_1, CANDIDATE_2), rejected=())
        request = _make_request()

        result = runtime.execute_plan(plan, request)

        assert result.winner == CANDIDATE_2
        assert result.content == "fallback response"
        assert result.fallback_occurred
        assert len(result.attempts) == 2
        assert not result.attempts[0].ok
        assert result.attempts[1].ok
        assert mock_transport.send_attempt.call_count == 2
        # Health store observed failure on first and success on second
        assert health_store.get_status("vm100_local_ollama", model="qwen3:8b") == ProviderHealthStatus.TIMEOUT
        assert health_store.get_status("gpu_ollama", model="qwen3:8b") == ProviderHealthStatus.REACHABLE

    def test_terminal_error_aborts_loop_immediately(self) -> None:
        mock_transport = MagicMock(spec=ProviderTransport)
        # First attempt fails with AUTH (fallback_eligible=False)
        mock_transport.send_attempt.return_value = _mock_error(
            CANDIDATE_1, kind=AiErrorKind.AUTH, fallback_eligible=False
        )

        runtime = SingleLoopRuntime(transport=mock_transport)
        plan = RoutePlan(eligible=(CANDIDATE_1, CANDIDATE_2), rejected=())
        request = _make_request()

        with pytest.raises(AllCandidatesExhaustedError, match="terminal error") as exc_info:
            runtime.execute_plan(plan, request)

        assert len(exc_info.value.attempts) == 1
        # Second candidate must NOT be called
        mock_transport.send_attempt.assert_called_once()

    def test_all_candidates_exhausted_raises_error_with_history(self) -> None:
        mock_transport = MagicMock(spec=ProviderTransport)
        mock_transport.send_attempt.side_effect = [
            _mock_error(CANDIDATE_1, kind=AiErrorKind.TIMEOUT, fallback_eligible=True),
            _mock_error(CANDIDATE_2, kind=AiErrorKind.SERVER, fallback_eligible=True),
        ]

        runtime = SingleLoopRuntime(transport=mock_transport)
        plan = RoutePlan(eligible=(CANDIDATE_1, CANDIDATE_2), rejected=())
        request = _make_request()

        with pytest.raises(AllCandidatesExhaustedError, match="All eligible provider candidates failed") as exc_info:
            runtime.execute_plan(plan, request)

        assert len(exc_info.value.attempts) == 2
        assert mock_transport.send_attempt.call_count == 2

    def test_deadline_budget_exceeded_before_fallback(self) -> None:
        mock_transport = MagicMock(spec=ProviderTransport)
        mock_transport.send_attempt.return_value = _mock_error(
            CANDIDATE_1, kind=AiErrorKind.TIMEOUT, fallback_eligible=True
        )

        mock_budget = MagicMock(spec=AttemptBudget)
        mock_budget.timeout_for_attempt.side_effect = [
            1.0,
            RequestDeadlineExceededError("No safe budget"),
        ]

        runtime = SingleLoopRuntime(transport=mock_transport)
        plan = RoutePlan(eligible=(CANDIDATE_1, CANDIDATE_2), rejected=())
        request = _make_request()

        with pytest.raises(RequestDeadlineExceededError, match="Shared request deadline exceeded") as exc_info:
            runtime.execute_plan(plan, request, budget=mock_budget)

        assert len(exc_info.value.attempts) == 1
        assert mock_transport.send_attempt.call_count == 1
