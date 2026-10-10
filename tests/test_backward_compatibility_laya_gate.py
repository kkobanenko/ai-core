"""Regression gate: J1 + routing unchanged when Laya shadow env is set."""

from __future__ import annotations

import pytest

from ai_core.judgment_contracts import JudgmentErrorCategory, JudgmentRequest, invoke_judgment
from ai_core.judgment_mock import MOCK_PROVIDER_ID, MockBehavior, MockVariant
from ai_core.judgment_contracts import BinaryQuestion
from ai_core.privacy import DataClass, OutboundForm
from ai_core.provider_catalog import NetworkBoundary


@pytest.fixture(autouse=True)
def _enable_laya_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_CORE_LAYA_J2_SHADOW_ADAPTER_ENABLED", "1")


def test_non_mock_provider_still_rejected_by_invoke_judgment() -> None:
    request = JudgmentRequest(
        request_id="req-1",
        decision_pack_id="pack-1",
        decision_pack_version="1",
        questions=(("q1", BinaryQuestion("entity")),),
        data_class=DataClass.SYNTHETIC,
        outbound_form=OutboundForm.RAW,
        network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
        request_egress_authorized=False,
        hosted_boundary=False,
        deadline_monotonic=200.0,
        provider="laya_multilingual_shadow",
        model="laya-multilingual",
        model_version="convaiinnovations-laya-multilingual-main",
        payload={"text": "x"},
    )
    response = invoke_judgment(request, decision_pack_known=lambda _a, _b: True, clock=lambda: 1.0)
    assert response.error is JudgmentErrorCategory.INVALID_REQUEST


def test_mock_timeout_semantics_unchanged() -> None:
    behavior = MockBehavior(variant=MockVariant.ERROR, error_category=JudgmentErrorCategory.PROVIDER_UNAVAILABLE)
    request = JudgmentRequest(
        request_id="req-1",
        decision_pack_id="pack-1",
        decision_pack_version="1",
        questions=(("q1", BinaryQuestion("entity")),),
        data_class=DataClass.SYNTHETIC,
        outbound_form=OutboundForm.RAW,
        network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
        request_egress_authorized=False,
        hosted_boundary=False,
        deadline_monotonic=200.0,
        provider=MOCK_PROVIDER_ID,
        model="fixture-model",
        model_version="1",
        payload={"note": "synthetic"},
    )
    response = invoke_judgment(
        request,
        mock_behavior=behavior,
        decision_pack_known=lambda _a, _b: True,
        clock=lambda: 1.0,
    )
    assert response.error is JudgmentErrorCategory.PROVIDER_UNAVAILABLE
