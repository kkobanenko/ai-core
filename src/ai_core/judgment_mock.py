"""Детерминированный in-memory mock judgment без сети и credentials."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from ai_core.judgment_contracts import (
    BinaryAnswer,
    ChoiceAnswer,
    JudgmentAnswer,
    JudgmentRequest,
    JudgmentResponse,
    ScoreAnswer,
)
from ai_core.judgment_errors import JudgmentError, JudgmentErrorCategory, judgment_error


@dataclass(frozen=True)
class JudgmentProviderOutcome:
    """Результат одной попытки вызова провайдера (до финальной валидации runtime)."""

    response: JudgmentResponse | None = None
    error: JudgmentError | None = None

    def __post_init__(self) -> None:
        has_response = self.response is not None
        has_error = self.error is not None
        if has_response == has_error:
            raise ValueError("exactly one of response or error must be set")


class MockJudgmentProvider:
    """Конфигурируемый mock для contract/policy тестов."""

    def __init__(
        self,
        *,
        answers_by_question: Mapping[str, JudgmentAnswer] | None = None,
        fixed_error: JudgmentError | None = None,
        simulate_deadline_exhausted: bool = False,
        monotonic_clock: Callable[[], float] | None = None,
    ) -> None:
        self._answers_by_question = dict(answers_by_question or {})
        self._fixed_error = fixed_error
        self._simulate_deadline_exhausted = simulate_deadline_exhausted
        self._monotonic_clock = monotonic_clock

    def invoke(
        self,
        request: JudgmentRequest,
        *,
        deadline_monotonic: float,
    ) -> JudgmentProviderOutcome:
        """Имитация провайдера; уважает общий deadline."""

        if self._simulate_deadline_exhausted:
            return JudgmentProviderOutcome(
                error=judgment_error(
                    JudgmentErrorCategory.DEADLINE_EXHAUSTED,
                    "mock provider observed exhausted deadline",
                )
            )
        if self._monotonic_clock is not None:
            now = self._monotonic_clock()
            if now > deadline_monotonic:
                return JudgmentProviderOutcome(
                    error=judgment_error(
                        JudgmentErrorCategory.DEADLINE_EXHAUSTED,
                        "mock provider observed exhausted deadline",
                    )
                )

        if self._fixed_error is not None:
            return JudgmentProviderOutcome(error=self._fixed_error)

        answers: dict[str, JudgmentAnswer] = {}
        for name in request.questions:
            if name not in self._answers_by_question:
                return JudgmentProviderOutcome(
                    error=judgment_error(
                        JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
                        "mock missing configured answer for question",
                    )
                )
            answers[name] = self._answers_by_question[name]

        response = JudgmentResponse(
            request_id=request.request_id,
            decision_pack=request.decision_pack,
            answers=answers,
            provider_pin=request.provider_pin,
            latency_ms=0.0,
            retry_count=0,
        )
        return JudgmentProviderOutcome(response=response)


def mock_judgment_provider(
    *,
    answers_by_question: Mapping[str, JudgmentAnswer] | None = None,
    fixed_error: JudgmentError | None = None,
    simulate_deadline_exhausted: bool = False,
    monotonic_clock: Callable[[], float] | None = None,
) -> MockJudgmentProvider:
    """Фабрика mock-провайдера для тестов."""

    return MockJudgmentProvider(
        answers_by_question=answers_by_question,
        fixed_error=fixed_error,
        simulate_deadline_exhausted=simulate_deadline_exhausted,
        monotonic_clock=monotonic_clock,
    )


__all__ = [
    "JudgmentProviderOutcome",
    "MockJudgmentProvider",
    "mock_judgment_provider",
]
