"""Privacy/egress для judgment."""

import time

from ai_core.judgment_contracts import (
    BinaryQuestion,
    DecisionPackRef,
    JudgmentExecutionMode,
    JudgmentProviderPin,
    JudgmentRequest,
)
from ai_core.judgment_errors import JudgmentErrorCategory
from ai_core.judgment_privacy import evaluate_judgment_privacy
from ai_core.privacy import DataClass, OutboundForm


def _request(
    *,
    execution_mode: JudgmentExecutionMode,
    data_class: DataClass,
    request_egress_authorized: bool,
) -> JudgmentRequest:
    return JudgmentRequest(
        request_id="req-privacy",
        decision_pack=DecisionPackRef("pack", "1"),
        shared_state={},
        questions={"q": BinaryQuestion()},
        provider_pin=JudgmentProviderPin(
            provider_id="mock_judgment",
            model="jev-1.13.0",
            model_version="0.7.1",
        ),
        execution_mode=execution_mode,
        data_class=data_class,
        outbound_form=OutboundForm.RAW,
        request_egress_authorized=request_egress_authorized,
        deadline_monotonic=time.monotonic() + 10.0,
    )


def test_local_mode_allows_non_secret() -> None:
    err = evaluate_judgment_privacy(
        _request(
            execution_mode=JudgmentExecutionMode.LOCAL_NO_EGRESS,
            data_class=DataClass.PRIVATE_CLIENT_DATA,
            request_egress_authorized=False,
        )
    )
    assert err is None


def test_secret_denied_even_locally() -> None:
    err = evaluate_judgment_privacy(
        _request(
            execution_mode=JudgmentExecutionMode.LOCAL_NO_EGRESS,
            data_class=DataClass.SECRET,
            request_egress_authorized=False,
        )
    )
    assert err is not None
    assert err.category is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED


def test_hosted_requires_eligible_class_and_egress_auth() -> None:
    err = evaluate_judgment_privacy(
        _request(
            execution_mode=JudgmentExecutionMode.HOSTED_EGRESS,
            data_class=DataClass.PRIVATE_CLIENT_DATA,
            request_egress_authorized=True,
        )
    )
    assert err is not None
    assert err.category is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED


def test_hosted_public_no_pii_with_egress_auth() -> None:
    err = evaluate_judgment_privacy(
        _request(
            execution_mode=JudgmentExecutionMode.HOSTED_EGRESS,
            data_class=DataClass.PUBLIC_NO_PII,
            request_egress_authorized=True,
        )
    )
    assert err is None
