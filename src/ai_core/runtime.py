"""S3 Single-Loop Runtime Engine: deterministic fallback over planned RouteCandidates.

Architectural invariants:
- Single Fallback Owner: Runtime is the sole loop owner; individual transports execute strictly one attempt.
- Strict Time Budget: All candidate attempts are bounded under a shared AttemptBudget.
- Fallback Decision Matrix: Proceed to next candidate if and only if attempt error has fallback_eligible=True.
- Comprehensive Telemetry: Returns ExecutionResult with full history of attempts, or raises AllCandidatesExhaustedError.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ai_core.budget import AttemptBudget
from ai_core.capabilities import ProviderCapability
from ai_core.errors import (
    AllCandidatesExhaustedError,
    NoEligibleProviderError,
    RequestDeadlineExceededError,
)
from ai_core.health import ProviderHealthStore
from ai_core.privacy import DataClass, OutboundForm
from ai_core.routing import RouteCandidate, RoutePlan
from ai_core.transports import (
    ProviderTransport,
    TransportAttemptResult,
    TransportRequest,
    TransportResponse,
    execute_transport_attempt,
)


@dataclass(frozen=True)
class ExecutionRequest:
    """High-level request input to the runtime execution engine."""

    messages: tuple[Mapping[str, str], ...]
    candidates: tuple[RouteCandidate, ...]
    capability: ProviderCapability = ProviderCapability.TEXT
    data_class: DataClass = DataClass.PUBLIC_NO_PII
    outbound_form: OutboundForm = OutboundForm.RAW
    total_timeout_seconds: float = 30.0
    temperature: float = 0.7
    extra_options: Mapping[str, Any] = field(default_factory=dict)
    request_egress_authorized: bool = False


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of a successful multi-candidate execution loop."""

    response: TransportResponse
    winner: RouteCandidate
    attempts: tuple[TransportAttemptResult, ...]
    total_latency_seconds: float

    @property
    def content(self) -> str:
        return self.response.content

    @property
    def fallback_occurred(self) -> bool:
        return len(self.attempts) > 1


class SingleLoopRuntime:
    """Deterministic single-loop executor over planned route candidates."""

    def __init__(
        self,
        health_store: ProviderHealthStore | None = None,
        transport: ProviderTransport | None = None,
    ) -> None:
        self.health_store = health_store or ProviderHealthStore()
        self.transport = transport

    def execute_plan(
        self,
        plan: RoutePlan,
        request: ExecutionRequest,
        *,
        budget: AttemptBudget | None = None,
        transport: ProviderTransport | None = None,
    ) -> ExecutionResult:
        """Execute candidates in plan.eligible until one succeeds or all fail."""
        if not plan.eligible:
            raise NoEligibleProviderError(
                "No candidate survived the explicit routing authorization, "
                "privacy, and health gates"
            )

        loop_start = time.monotonic()
        active_budget = budget or AttemptBudget.from_timeout(
            now_monotonic=loop_start,
            total_timeout_seconds=request.total_timeout_seconds,
        )

        resolved_transport = transport or self.transport
        attempts: list[TransportAttemptResult] = []
        eligible_candidates = plan.eligible
        total_candidates = len(eligible_candidates)

        for index, candidate in enumerate(eligible_candidates):
            now = time.monotonic()
            remaining_after_this = total_candidates - index - 1

            try:
                attempt_timeout = active_budget.timeout_for_attempt(
                    now_monotonic=now,
                    configured_timeout_seconds=request.total_timeout_seconds,
                    future_attempts=remaining_after_this,
                )
            except RequestDeadlineExceededError:
                if attempts:
                    raise AllCandidatesExhaustedError(
                        "Shared request deadline exceeded after failed attempts",
                        attempts=tuple(attempts),
                    )
                raise

            transport_req = TransportRequest(
                candidate=candidate,
                messages=request.messages,
                temperature=request.temperature,
                timeout_seconds=attempt_timeout,
                extra_options=request.extra_options,
            )

            result = execute_transport_attempt(
                transport_req,
                transport=resolved_transport,
                health_store=self.health_store,
            )
            attempts.append(result)

            if result.ok and result.response is not None:
                total_latency = time.monotonic() - loop_start
                return ExecutionResult(
                    response=result.response,
                    winner=candidate,
                    attempts=tuple(attempts),
                    total_latency_seconds=total_latency,
                )

            # Attempt failed. Check if fallback to next candidate is permissible.
            error_desc = result.error
            if error_desc is not None and not error_desc.fallback_eligible:
                # Terminal error (e.g. invalid input, auth failure) aborts immediately.
                raise AllCandidatesExhaustedError(
                    f"Candidate {candidate.provider_id} encountered terminal error ({error_desc.kind.value}); fallback aborted",
                    attempts=tuple(attempts),
                )

        raise AllCandidatesExhaustedError(
            "All eligible provider candidates failed during execution",
            attempts=tuple(attempts),
        )


__all__ = [
    "ExecutionRequest",
    "ExecutionResult",
    "SingleLoopRuntime",
]
