"""Runtime judgment J1: один deadline, privacy до провайдера, детерминированный mock."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from ai_core.judgment_contracts import JudgmentRequest, JudgmentResponse
from ai_core.judgment_errors import JudgmentError, JudgmentErrorCategory, judgment_error
from ai_core.judgment_mock import JudgmentProviderOutcome
from ai_core.judgment_privacy import evaluate_judgment_privacy
from ai_core.judgment_telemetry import (
    build_error_telemetry_event,
    build_success_telemetry_event,
    is_retryable_error,
)
from ai_core.judgment_validation import validate_judgment_request, validate_judgment_response


class JudgmentProvider(Protocol):
    """Абстракция провайдера; J1 реализует только mock."""

    def invoke(
        self,
        request: JudgmentRequest,
        *,
        deadline_monotonic: float,
    ) -> JudgmentProviderOutcome:
        ...


@dataclass(frozen=True)
class JudgmentExecutionResult:
    """Итог выполнения: успех или нормализованная ошибка + metadata telemetry."""

    response: JudgmentResponse | None
    error: JudgmentError | None
    telemetry: Mapping[str, Any]

    def __post_init__(self) -> None:
        has_response = self.response is not None
        has_error = self.error is not None
        if has_response == has_error:
            raise ValueError("exactly one of response or error must be set")


def execute_judgment(
    request: JudgmentRequest,
    provider: JudgmentProvider,
    *,
    monotonic_clock: Callable[[], float] = time.monotonic,
    max_retries: int = 2,
) -> JudgmentExecutionResult:
    """Один владелец retry/fallback внутри общего monotonic deadline."""

    started = monotonic_clock()
    retry_count = 0

    def _finish_error(
        error: JudgmentError,
        *,
        latency_ms: float,
        retries: int,
    ) -> JudgmentExecutionResult:
        pin = request.provider_pin
        pack = request.decision_pack
        telemetry = build_error_telemetry_event(
            error,
            request_id=request.request_id,
            decision_pack_id=pack.decision_pack_id,
            decision_pack_version=pack.decision_pack_version,
            provider_id=pin.provider_id,
            model=pin.model,
            model_version=pin.model_version,
            latency_ms=latency_ms,
            retry_count=retries,
        )
        return JudgmentExecutionResult(response=None, error=error, telemetry=telemetry)

    now = monotonic_clock()
    validation_error = validate_judgment_request(request, now_monotonic=now)
    if validation_error is not None:
        return _finish_error(
            validation_error,
            latency_ms=(monotonic_clock() - started) * 1000.0,
            retries=retry_count,
        )

    privacy_error = evaluate_judgment_privacy(request)
    if privacy_error is not None:
        return _finish_error(
            privacy_error,
            latency_ms=(monotonic_clock() - started) * 1000.0,
            retries=retry_count,
        )

    last_error: JudgmentError | None = None
    while True:
        now = monotonic_clock()
        if now > request.deadline_monotonic:
            if last_error is not None:
                return _finish_error(
                    last_error,
                    latency_ms=(now - started) * 1000.0,
                    retries=retry_count,
                )
            return _finish_error(
                judgment_error(
                    JudgmentErrorCategory.DEADLINE_EXHAUSTED,
                    "total judgment deadline exhausted",
                ),
                latency_ms=(now - started) * 1000.0,
                retries=retry_count,
            )

        outcome = provider.invoke(
            request,
            deadline_monotonic=request.deadline_monotonic,
        )

        if outcome.error is not None:
            last_error = outcome.error
            if (
                is_retryable_error(outcome.error.category)
                and retry_count < max_retries
                and monotonic_clock() < request.deadline_monotonic
            ):
                retry_count += 1
                continue
            return _finish_error(
                outcome.error,
                latency_ms=(monotonic_clock() - started) * 1000.0,
                retries=retry_count,
            )

        if outcome.response is None:
            return _finish_error(
                judgment_error(
                    JudgmentErrorCategory.INTERNAL_ERROR,
                    "provider returned empty outcome",
                ),
                latency_ms=(monotonic_clock() - started) * 1000.0,
                retries=retry_count,
            )

        response = JudgmentResponse(
            request_id=outcome.response.request_id,
            decision_pack=outcome.response.decision_pack,
            answers=outcome.response.answers,
            provider_pin=outcome.response.provider_pin,
            latency_ms=(monotonic_clock() - started) * 1000.0,
            retry_count=retry_count,
        )

        response_error = validate_judgment_response(request, response)
        if response_error is not None:
            return _finish_error(
                response_error,
                latency_ms=response.latency_ms,
                retries=retry_count,
            )

        telemetry = build_success_telemetry_event(response)
        return JudgmentExecutionResult(
            response=response,
            error=None,
            telemetry=telemetry,
        )


__all__ = [
    "JudgmentExecutionResult",
    "JudgmentProvider",
    "execute_judgment",
]
