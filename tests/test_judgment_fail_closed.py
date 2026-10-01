"""Fail-closed поведение judgment J1."""

import time

from ai_core.judgment_contracts import (
    BinaryAnswer,
    BinaryQuestion,
    DecisionPackRef,
    JudgmentExecutionMode,
    JudgmentProviderPin,
    JudgmentRequest,
)
from ai_core.judgment_errors import JudgmentErrorCategory, judgment_error
from ai_core.judgment_mock import mock_judgment_provider
from ai_core.judgment_runtime import execute_judgment
from ai_core.privacy import DataClass, OutboundForm


def _local_request() -> JudgmentRequest:
    return JudgmentRequest(
        request_id="fc-1",
        decision_pack=DecisionPackRef("pack", "1"),
        shared_state={"state": "x"},
        questions={"q": BinaryQuestion()},
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


def test_invalid_request_never_calls_provider() -> None:
    called = {"n": 0}

    class SpyProvider:
        def invoke(self, request, *, deadline_monotonic):
            called["n"] += 1
            return mock_judgment_provider(
                answers_by_question={"q": BinaryAnswer(probability_true=0.5)}
            ).invoke(request, deadline_monotonic=deadline_monotonic)

    bad = _local_request()
    bad = JudgmentRequest(
        request_id="",
        decision_pack=bad.decision_pack,
        shared_state=bad.shared_state,
        questions=bad.questions,
        provider_pin=bad.provider_pin,
        execution_mode=bad.execution_mode,
        data_class=bad.data_class,
        outbound_form=bad.outbound_form,
        request_egress_authorized=bad.request_egress_authorized,
        deadline_monotonic=bad.deadline_monotonic,
    )
    result = execute_judgment(bad, SpyProvider())
    assert result.response is None
    assert result.error.category is JudgmentErrorCategory.INVALID_REQUEST
    assert called["n"] == 0


def test_privacy_denial_before_provider() -> None:
    called = {"n": 0}

    class SpyProvider:
        def invoke(self, request, *, deadline_monotonic):
            called["n"] += 1
            return mock_judgment_provider(
                answers_by_question={"q": BinaryAnswer(probability_true=0.5)}
            ).invoke(request, deadline_monotonic=deadline_monotonic)

    request = JudgmentRequest(
        request_id="fc-2",
        decision_pack=DecisionPackRef("pack", "1"),
        shared_state={},
        questions={"q": BinaryQuestion()},
        provider_pin=JudgmentProviderPin(
            provider_id="mock_judgment",
            model="jev-1.13.0",
            model_version="0.7.1",
        ),
        execution_mode=JudgmentExecutionMode.HOSTED_EGRESS,
        data_class=DataClass.PRIVATE_CLIENT_DATA,
        outbound_form=OutboundForm.RAW,
        request_egress_authorized=True,
        deadline_monotonic=time.monotonic() + 30.0,
    )
    result = execute_judgment(request, SpyProvider())
    assert result.error.category is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED
    assert called["n"] == 0


def test_invalid_provider_response_not_exposed() -> None:
    provider = mock_judgment_provider(
        answers_by_question={"q": BinaryAnswer(probability_true=1.5)}
    )
    result = execute_judgment(_local_request(), provider)
    assert result.response is None
    assert result.error.category is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_deadline_exhausted_mock() -> None:
    provider = mock_judgment_provider(simulate_deadline_exhausted=True)
    result = execute_judgment(_local_request(), provider)
    assert result.error.category is JudgmentErrorCategory.DEADLINE_EXHAUSTED


def test_normalized_provider_error_fixture() -> None:
    provider = mock_judgment_provider(
        fixed_error=judgment_error(
            JudgmentErrorCategory.AUTHENTICATION_FAILED,
            "mock auth failed",
        )
    )
    result = execute_judgment(_local_request(), provider)
    assert result.error.category is JudgmentErrorCategory.AUTHENTICATION_FAILED
