"""Runtime judgment с mock-провайдером."""

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
    ScoreAnswer,
    ScoreQuestion,
)
from ai_core.judgment_errors import JudgmentErrorCategory, judgment_error
from ai_core.judgment_mock import mock_judgment_provider
from ai_core.judgment_runtime import execute_judgment
from ai_core.privacy import DataClass, OutboundForm


def _request(questions, answers) -> JudgmentRequest:
    return JudgmentRequest(
        request_id="req-runtime",
        decision_pack=DecisionPackRef("pack", "1"),
        shared_state={"k": "v"},
        questions=questions,
        provider_pin=JudgmentProviderPin(
            provider_id="mock_judgment",
            model="jev-1.13.0",
            model_version="0.7.1",
        ),
        execution_mode=JudgmentExecutionMode.LOCAL_NO_EGRESS,
        data_class=DataClass.SYNTHETIC,
        outbound_form=OutboundForm.RAW,
        request_egress_authorized=False,
        deadline_monotonic=time.monotonic() + 30.0,
    )


def test_execute_binary_batch_success() -> None:
    questions = {"b": BinaryQuestion()}
    answers = {"b": BinaryAnswer(probability_true=0.7)}
    request = _request(questions, answers)
    provider = mock_judgment_provider(answers_by_question=answers)
    result = execute_judgment(request, provider)
    assert result.error is None
    assert result.response is not None
    assert result.response.answers["b"].probability_true == 0.7


def test_execute_choice_batch_success() -> None:
    questions = {"c": ChoiceQuestion(choices=("yes", "no"))}
    answers = {
        "c": ChoiceAnswer(
            selected="yes",
            confidence=0.8,
            probabilities={"yes": 0.8, "no": 0.2},
        )
    }
    request = _request(questions, answers)
    provider = mock_judgment_provider(answers_by_question=answers)
    result = execute_judgment(request, provider)
    assert result.error is None
    assert result.response is not None


def test_execute_score_batch_success() -> None:
    questions = {
        "s": ScoreQuestion(levels=("low", "high"), min_score=0.0, max_score=1.0)
    }
    answers = {
        "s": ScoreAnswer(
            expected_score=0.6,
            confidence=0.7,
            probabilities={"low": 0.4, "high": 0.6},
        )
    }
    request = _request(questions, answers)
    provider = mock_judgment_provider(answers_by_question=answers)
    result = execute_judgment(request, provider)
    assert result.error is None


def test_provider_error_surfaces_without_partial_answers() -> None:
    request = _request({"b": BinaryQuestion()}, {})
    provider = mock_judgment_provider(
        fixed_error=judgment_error(
            JudgmentErrorCategory.PROVIDER_UNAVAILABLE,
            "mock unavailable",
        )
    )
    result = execute_judgment(request, provider)
    assert result.response is None
    assert result.error is not None
    assert result.error.category is JudgmentErrorCategory.PROVIDER_UNAVAILABLE


def test_retryable_error_retries_within_deadline() -> None:
    call_count = {"n": 0}

    class FlakyProvider:
        def invoke(self, request, *, deadline_monotonic):
            call_count["n"] += 1
            if call_count["n"] == 1:
                from ai_core.judgment_mock import JudgmentProviderOutcome

                return JudgmentProviderOutcome(
                    error=judgment_error(
                        JudgmentErrorCategory.RATE_LIMITED,
                        "mock rate limit",
                    )
                )
            return mock_judgment_provider(
                answers_by_question={"b": BinaryAnswer(probability_true=0.1)}
            ).invoke(request, deadline_monotonic=deadline_monotonic)

    request = _request({"b": BinaryQuestion()}, {})
    result = execute_judgment(request, FlakyProvider())
    assert result.error is None
    assert call_count["n"] >= 2
