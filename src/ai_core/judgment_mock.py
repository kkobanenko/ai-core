"""Детерминированный мок J1. Только тесты. Не провайдер каталога.

Сети, секретов, SDK и произвольного callback здесь нет.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from ai_core.judgment_contracts import (
    BinaryAnswer,
    BinaryQuestion,
    ChoiceAnswer,
    ChoiceQuestion,
    JudgmentErrorCategory,
    JudgmentOutcome,
    JudgmentRequest,
    JudgmentResponse,
    JudgmentTelemetry,
    ScoreAnswer,
    ScoreQuestion,
)

MOCK_PROVIDER_ID = "mock_judgment"


class MockVariant(str, Enum):
    """Какой фиктивный результат собрать."""

    SUCCESS = "success"
    ERROR = "error"
    INVALID_RESPONSE = "invalid_response"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class MockBehavior:
    """Данные поведения мока. Это не исполняемый код потребителя."""

    variant: MockVariant = MockVariant.SUCCESS
    error_category: JudgmentErrorCategory = JudgmentErrorCategory.PROVIDER_UNAVAILABLE
    timeout_seconds: float = 0.05
    binary_probability: float = 1.0


class DeterministicMockJudgmentProvider:
    """Репозиторный мок. Не ходит в сеть и не читает окружение."""

    def __init__(self, behavior: MockBehavior | None = None) -> None:
        self.behavior = behavior or MockBehavior()

    def judge(self, request: JudgmentRequest) -> JudgmentResponse:
        behavior = self.behavior
        if behavior.variant is MockVariant.TIMEOUT:
            time.sleep(behavior.timeout_seconds)
        if behavior.variant is MockVariant.ERROR:
            return _error_response(request, behavior.error_category)
        if behavior.variant is MockVariant.INVALID_RESPONSE:
            return _invalid_response(request)
        return _success_response(request, behavior.binary_probability)


def _telemetry(request: JudgmentRequest, outcome: JudgmentOutcome, error: JudgmentErrorCategory | None) -> JudgmentTelemetry:
    return JudgmentTelemetry(
        outcome=outcome,
        error_category=error,
        latency_ms=0,
        retry_count=0,
        provider=request.provider,
        model=request.model,
        model_version=request.model_version,
        decision_pack_id=request.decision_pack_id,
        decision_pack_version=request.decision_pack_version,
    )


def _shell(request: JudgmentRequest, outcome: JudgmentOutcome, error: JudgmentErrorCategory | None) -> dict:
    return {
        "provider": request.provider,
        "model": request.model,
        "model_version": request.model_version,
        "decision_pack_id": request.decision_pack_id,
        "decision_pack_version": request.decision_pack_version,
        "telemetry": _telemetry(request, outcome, error),
    }


def _error_response(request: JudgmentRequest, category: JudgmentErrorCategory) -> JudgmentResponse:
    return JudgmentResponse(answers=None, error=category, **_shell(request, JudgmentOutcome.ERROR, category))


def _invalid_response(request: JudgmentRequest) -> JudgmentResponse:
    # Намеренно битый ответ: бинарная вероятность вне диапазона, если вопрос бинарный,
    # иначе чужой вариант ответа.
    answers = []
    for name, question in request.questions:
        if isinstance(question, BinaryQuestion):
            answers.append((name, BinaryAnswer(2.0)))
        else:
            answers.append((name, BinaryAnswer(1.0)))
    return JudgmentResponse(
        answers=tuple(answers),
        error=None,
        **_shell(request, JudgmentOutcome.SUCCESS, None),
    )


def _success_response(request: JudgmentRequest, binary_probability: float) -> JudgmentResponse:
    answers = []
    for name, question in request.questions:
        if isinstance(question, BinaryQuestion):
            answers.append((name, BinaryAnswer(binary_probability)))
        elif isinstance(question, ChoiceQuestion):
            selected = question.choices[0]
            probabilities = tuple(sorted((choice, 1.0 if choice == selected else 0.0) for choice in question.choices))
            answers.append((name, ChoiceAnswer(selected, 1.0, probabilities)))
        elif isinstance(question, ScoreQuestion):
            selected = question.levels[0]
            probabilities = tuple(sorted((level, 1.0 if level == selected else 0.0) for level in question.levels))
            answers.append((name, ScoreAnswer(question.minimum, 1.0, probabilities)))
    return JudgmentResponse(
        answers=tuple(answers),
        error=None,
        **_shell(request, JudgmentOutcome.SUCCESS, None),
    )
