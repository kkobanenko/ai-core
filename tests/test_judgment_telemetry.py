"""Telemetry judgment — только метаданные."""

import time

from ai_core.judgment_contracts import (
    BinaryAnswer,
    BinaryQuestion,
    DecisionPackRef,
    JudgmentExecutionMode,
    JudgmentProviderPin,
    JudgmentRequest,
    JudgmentResponse,
)
from ai_core.judgment_errors import JudgmentErrorCategory, judgment_error
from ai_core.judgment_runtime import execute_judgment
from ai_core.judgment_telemetry import build_error_telemetry_event, build_success_telemetry_event
from ai_core.judgment_mock import mock_judgment_provider
from ai_core.privacy import DataClass, OutboundForm


def test_success_telemetry_excludes_semantic_payload() -> None:
    response = JudgmentResponse(
        request_id="r1",
        decision_pack=DecisionPackRef("p", "1"),
        answers={"q": BinaryAnswer(probability_true=0.5)},
        provider_pin=JudgmentProviderPin("mock", "m", "v"),
        latency_ms=3.0,
        retry_count=0,
    )
    event = build_success_telemetry_event(response)
    assert "probability_true" not in event
    assert event["outcome"] == "success"
    assert event["model_version"] == "v"


def test_error_telemetry_has_category_only() -> None:
    event = build_error_telemetry_event(
        judgment_error(JudgmentErrorCategory.INVALID_REQUEST, "bad"),
        request_id="r1",
        decision_pack_id="p",
        decision_pack_version="1",
        provider_id="mock",
        model="m",
        model_version="v",
        latency_ms=1.0,
        retry_count=0,
    )
    assert event["error_category"] == "invalid_request"


def test_runtime_telemetry_on_success() -> None:
    request = JudgmentRequest(
        request_id="r2",
        decision_pack=DecisionPackRef("p", "1"),
        shared_state={},
        questions={"q": BinaryQuestion()},
        provider_pin=JudgmentProviderPin("mock_judgment", "jev-1.13.0", "0.7.1"),
        execution_mode=JudgmentExecutionMode.LOCAL_NO_EGRESS,
        data_class=DataClass.SYNTHETIC,
        outbound_form=OutboundForm.RAW,
        request_egress_authorized=False,
        deadline_monotonic=time.monotonic() + 10.0,
    )
    provider = mock_judgment_provider(
        answers_by_question={"q": BinaryAnswer(probability_true=0.2)}
    )
    result = execute_judgment(request, provider)
    assert "probabilities" not in result.telemetry
    assert result.telemetry["decision_pack_id"] == "p"
