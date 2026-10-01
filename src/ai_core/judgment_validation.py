"""Детерминированная валидация запросов и ответов judgment."""

from __future__ import annotations

import math
import re
from typing import Mapping

from ai_core.judgment_contracts import (
    PROBABILITY_SUM_TOLERANCE,
    AnswerKind,
    BinaryAnswer,
    BinaryQuestion,
    ChoiceAnswer,
    ChoiceQuestion,
    JudgmentAnswer,
    JudgmentProviderPin,
    JudgmentQuestion,
    JudgmentRequest,
    JudgmentResponse,
    QuestionKind,
    ScoreAnswer,
    ScoreQuestion,
)
from ai_core.judgment_errors import JudgmentError, JudgmentErrorCategory, judgment_error

_LATEST_PATTERN = re.compile(r"(^latest$|[-_]latest$|\*|\?)", re.IGNORECASE)


def _is_finite(value: float) -> bool:
    return math.isfinite(value)


def _in_unit_interval(value: float) -> bool:
    return _is_finite(value) and 0.0 <= value <= 1.0


def validate_provider_pin(pin: JudgmentProviderPin) -> JudgmentError | None:
    """Проверить точные pin без wildcards и latest-алиасов."""

    for field_name, raw in (
        ("provider_id", pin.provider_id),
        ("model", pin.model),
        ("model_version", pin.model_version),
    ):
        if not isinstance(raw, str) or not raw.strip():
            return judgment_error(
                JudgmentErrorCategory.INVALID_REQUEST,
                f"{field_name} must be a non-empty exact pin",
            )
        if _LATEST_PATTERN.search(raw.strip()):
            return judgment_error(
                JudgmentErrorCategory.INVALID_REQUEST,
                f"{field_name} must not use latest or wildcard selectors",
            )
    return None


def validate_shared_state(shared_state: Mapping[str, str]) -> JudgmentError | None:
    """Провайдер-нейтральная проверка shared state (строковые пары)."""

    if not isinstance(shared_state, Mapping):
        return judgment_error(
            JudgmentErrorCategory.INVALID_REQUEST,
            "shared_state must be a mapping",
        )
    for key, value in shared_state.items():
        if not isinstance(key, str) or not key.strip():
            return judgment_error(
                JudgmentErrorCategory.INVALID_REQUEST,
                "shared_state keys must be non-empty strings",
            )
        if not isinstance(value, str):
            return judgment_error(
                JudgmentErrorCategory.INVALID_REQUEST,
                "shared_state values must be strings",
            )
    return None


def validate_judgment_request(
    request: JudgmentRequest,
    *,
    now_monotonic: float,
) -> JudgmentError | None:
    """Локальная валидация запроса до вызова провайдера."""

    if not isinstance(request.request_id, str) or not request.request_id.strip():
        return judgment_error(
            JudgmentErrorCategory.INVALID_REQUEST,
            "request_id must be non-empty",
        )

    pack = request.decision_pack
    if not pack.decision_pack_id.strip() or not pack.decision_pack_version.strip():
        return judgment_error(
            JudgmentErrorCategory.INVALID_REQUEST,
            "decision_pack id and version must be non-empty",
        )

    pin_error = validate_provider_pin(request.provider_pin)
    if pin_error is not None:
        return pin_error

    state_error = validate_shared_state(request.shared_state)
    if state_error is not None:
        return state_error

    if not isinstance(request.questions, Mapping) or not request.questions:
        return judgment_error(
            JudgmentErrorCategory.INVALID_REQUEST,
            "at least one question is required",
        )

    for name, question in request.questions.items():
        if not isinstance(name, str) or not name.strip():
            return judgment_error(
                JudgmentErrorCategory.INVALID_REQUEST,
                "question names must be non-empty",
            )
        if not isinstance(
            question, (BinaryQuestion, ChoiceQuestion, ScoreQuestion)
        ):
            return judgment_error(
                JudgmentErrorCategory.INVALID_REQUEST,
                "unsupported question variant",
            )

    if not _is_finite(request.deadline_monotonic):
        return judgment_error(
            JudgmentErrorCategory.INVALID_REQUEST,
            "deadline_monotonic must be finite",
        )
    if now_monotonic > request.deadline_monotonic:
        return judgment_error(
            JudgmentErrorCategory.DEADLINE_EXHAUSTED,
            "total deadline already exhausted before execution",
        )

    return None


def _question_kind(question: JudgmentQuestion) -> QuestionKind:
    if isinstance(question, BinaryQuestion):
        return QuestionKind.BINARY
    if isinstance(question, ChoiceQuestion):
        return QuestionKind.CHOICE
    return QuestionKind.SCORE


def _answer_kind(answer: JudgmentAnswer) -> AnswerKind:
    if isinstance(answer, BinaryAnswer):
        return AnswerKind.BINARY
    if isinstance(answer, ChoiceAnswer):
        return AnswerKind.CHOICE
    return AnswerKind.SCORE


def validate_binary_answer(answer: BinaryAnswer) -> JudgmentError | None:
    if not _in_unit_interval(answer.probability_true):
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "binary probability_true must be finite in [0, 1]",
        )
    return None


def validate_choice_answer(
    question: ChoiceQuestion,
    answer: ChoiceAnswer,
) -> JudgmentError | None:
    if answer.selected not in question.choices:
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "selected choice must be one of declared choices",
        )
    if not _in_unit_interval(answer.confidence):
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "choice confidence must be finite in [0, 1]",
        )
    expected = set(question.choices)
    if set(answer.probabilities.keys()) != expected:
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "choice probabilities must cover exactly all declared choices",
        )
    total = 0.0
    for choice in question.choices:
        prob = answer.probabilities[choice]
        if not _in_unit_interval(prob):
            return judgment_error(
                JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
                "each choice probability must be finite in [0, 1]",
            )
        total += prob
    if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "choice probability distribution must sum to approximately 1",
        )
    return None


def validate_score_answer(
    question: ScoreQuestion,
    answer: ScoreAnswer,
) -> JudgmentError | None:
    if not _is_finite(answer.expected_score):
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "expected_score must be finite",
        )
    if not (question.min_score <= answer.expected_score <= question.max_score):
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "expected_score must be within declared bounds",
        )
    if not _in_unit_interval(answer.confidence):
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "score confidence must be finite in [0, 1]",
        )
    expected = set(question.levels)
    if set(answer.probabilities.keys()) != expected:
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "score probabilities must cover exactly all declared levels",
        )
    total = 0.0
    for level in question.levels:
        prob = answer.probabilities[level]
        if not _in_unit_interval(prob):
            return judgment_error(
                JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
                "each level probability must be finite in [0, 1]",
            )
        total += prob
    if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "score probability distribution must sum to approximately 1",
        )
    return None


def validate_judgment_response(
    request: JudgmentRequest,
    response: JudgmentResponse,
) -> JudgmentError | None:
    """Сопоставить ответ с запросом; без лишних ответов и сырых текстов провайдера."""

    if response.request_id != request.request_id:
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "response request_id mismatch",
        )
    if response.decision_pack != request.decision_pack:
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "response decision_pack mismatch",
        )
    if response.provider_pin != request.provider_pin:
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "response provider pin mismatch",
        )

    if set(response.answers.keys()) != set(request.questions.keys()):
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "answers must match requested question names exactly",
        )

    for name, question in request.questions.items():
        answer = response.answers[name]
        if _question_kind(question) != _answer_kind(answer):
            return judgment_error(
                JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
                "answer variant must match question variant",
            )
        if isinstance(question, BinaryQuestion) and isinstance(answer, BinaryAnswer):
            err = validate_binary_answer(answer)
        elif isinstance(question, ChoiceQuestion) and isinstance(answer, ChoiceAnswer):
            err = validate_choice_answer(question, answer)
        elif isinstance(question, ScoreQuestion) and isinstance(answer, ScoreAnswer):
            err = validate_score_answer(question, answer)
        else:
            err = judgment_error(
                JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
                "incompatible question and answer types",
            )
        if err is not None:
            return err

    if not _is_finite(response.latency_ms) or response.latency_ms < 0:
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "latency_ms must be a finite non-negative number",
        )
    if response.retry_count < 0:
        return judgment_error(
            JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE,
            "retry_count must be non-negative",
        )

    return None


__all__ = [
    "validate_binary_answer",
    "validate_choice_answer",
    "validate_judgment_request",
    "validate_judgment_response",
    "validate_provider_pin",
    "validate_score_answer",
    "validate_shared_state",
]
