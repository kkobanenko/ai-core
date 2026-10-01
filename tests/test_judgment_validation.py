"""Валидация запросов и ответов judgment."""

import time

from ai_core.judgment_contracts import (
    BinaryAnswer,
    BinaryQuestion,
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionPackRef,
    JudgmentExecutionMode,
    JudgmentProviderPin,
    JudgmentRequest,
    JudgmentResponse,
    ScoreAnswer,
    ScoreQuestion,
)
from ai_core.judgment_errors import JudgmentErrorCategory
from ai_core.judgment_validation import (
    validate_judgment_request,
    validate_judgment_response,
    validate_provider_pin,
)
from ai_core.privacy import DataClass, OutboundForm


def _base_request(**overrides) -> JudgmentRequest:
    now = time.monotonic()
    payload = {
        "request_id": "req-1",
        "decision_pack": DecisionPackRef("pack-a", "v1"),
        "shared_state": {"ctx": "opaque"},
        "questions": {"q1": BinaryQuestion()},
        "provider_pin": JudgmentProviderPin(
            provider_id="mock_judgment",
            model="jev-1.13.0",
            model_version="0.7.1",
        ),
        "execution_mode": JudgmentExecutionMode.LOCAL_NO_EGRESS,
        "data_class": DataClass.SYNTHETIC,
        "outbound_form": OutboundForm.RAW,
        "request_egress_authorized": False,
        "deadline_monotonic": now + 30.0,
    }
    payload.update(overrides)
    return JudgmentRequest(**payload)


def test_rejects_latest_pin() -> None:
    pin = JudgmentProviderPin(
        provider_id="mock",
        model="jev-latest",
        model_version="1.0.0",
    )
    err = validate_provider_pin(pin)
    assert err is not None
    assert err.category is JudgmentErrorCategory.INVALID_REQUEST


def test_request_requires_non_empty_questions() -> None:
    request = _base_request(questions={})
    err = validate_judgment_request(request, now_monotonic=time.monotonic())
    assert err is not None
    assert err.category is JudgmentErrorCategory.INVALID_REQUEST


def test_expired_deadline_before_execution() -> None:
    request = _base_request(deadline_monotonic=time.monotonic() - 1.0)
    err = validate_judgment_request(request, now_monotonic=time.monotonic())
    assert err is not None
    assert err.category is JudgmentErrorCategory.DEADLINE_EXHAUSTED


def test_response_variant_must_match_question() -> None:
    request = _base_request(
        questions={"q1": ChoiceQuestion(choices=("a", "b"))},
    )
    response = JudgmentResponse(
        request_id=request.request_id,
        decision_pack=request.decision_pack,
        answers={
            "q1": BinaryAnswer(probability_true=0.5),
        },
        provider_pin=request.provider_pin,
        latency_ms=1.0,
        retry_count=0,
    )
    err = validate_judgment_response(request, response)
    assert err is not None
    assert err.category is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_choice_probabilities_must_sum_to_one() -> None:
    question = ChoiceQuestion(choices=("a", "b"))
    answer = ChoiceAnswer(
        selected="a",
        confidence=0.5,
        probabilities={"a": 0.4, "b": 0.4},
    )
    request = _base_request(questions={"q1": question})
    response = JudgmentResponse(
        request_id=request.request_id,
        decision_pack=request.decision_pack,
        answers={"q1": answer},
        provider_pin=request.provider_pin,
        latency_ms=1.0,
        retry_count=0,
    )
    err = validate_judgment_response(request, response)
    assert err is not None


def test_score_expected_within_bounds() -> None:
    question = ScoreQuestion(levels=("low", "high"), min_score=0.0, max_score=1.0)
    answer = ScoreAnswer(
        expected_score=2.0,
        confidence=0.5,
        probabilities={"low": 0.5, "high": 0.5},
    )
    request = _base_request(questions={"q1": question})
    response = JudgmentResponse(
        request_id=request.request_id,
        decision_pack=request.decision_pack,
        answers={"q1": answer},
        provider_pin=request.provider_pin,
        latency_ms=1.0,
        retry_count=0,
    )
    err = validate_judgment_response(request, response)
    assert err is not None
