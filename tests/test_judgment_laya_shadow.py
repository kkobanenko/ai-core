"""J2 shadow Laya adapter tests (HTTP transport mock, no laya/torch import)."""

from __future__ import annotations

import json
import os

import pytest

from ai_core.judgment_contracts import (
    BinaryQuestion,
    JudgmentErrorCategory,
    JudgmentRequest,
    invoke_judgment,
)
from ai_core.judgment_laya_shadow import (
    LAYA_SHADOW_MODEL_ID,
    LAYA_SHADOW_MODEL_VERSION,
    LAYA_SHADOW_PROVIDER_ID,
    invoke_laya_shadow_judgment,
    laya_shadow_adapter_enabled,
)
from ai_core.judgment_mock import MOCK_PROVIDER_ID
from ai_core.privacy import DataClass, OutboundForm
from ai_core.provider_catalog import NetworkBoundary


def _binary_request(**overrides: object) -> JudgmentRequest:
    base = {
        "request_id": "req-laya-1",
        "decision_pack_id": "pack-1",
        "decision_pack_version": "1",
        "questions": (("q1", BinaryQuestion("same entity")),),
        "data_class": DataClass.PUBLIC_NO_PII,
        "outbound_form": OutboundForm.SANITIZED,
        "network_boundary": NetworkBoundary.LOCAL_SAME_HOST,
        "request_egress_authorized": False,
        "hosted_boundary": False,
        "deadline_monotonic": 10_000.0,
        "provider": LAYA_SHADOW_PROVIDER_ID,
        "model": LAYA_SHADOW_MODEL_ID,
        "model_version": LAYA_SHADOW_MODEL_VERSION,
        "payload": {"text": "sanitized sample"},
    }
    base.update(overrides)
    return JudgmentRequest(**base)


def test_adapter_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_CORE_LAYA_J2_SHADOW_ADAPTER_ENABLED", raising=False)
    assert laya_shadow_adapter_enabled() is False
    response = invoke_laya_shadow_judgment(
        _binary_request(),
        decision_pack_known=lambda _a, _b: True,
    )
    assert response.error is JudgmentErrorCategory.INVALID_REQUEST


def test_invoke_judgment_unchanged_for_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_CORE_LAYA_J2_SHADOW_ADAPTER_ENABLED", "1")
    request = JudgmentRequest(
        request_id="req-1",
        decision_pack_id="pack-1",
        decision_pack_version="1",
        questions=(("q1", BinaryQuestion("same entity")),),
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
    response = invoke_judgment(request, decision_pack_known=lambda _a, _b: True, clock=lambda: 1.0)
    assert response.error is None
    assert response.answers is not None


def test_laya_shadow_success_with_mock_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_CORE_LAYA_J2_SHADOW_ADAPTER_ENABLED", "1")

    def fake_post(_url: str, body: bytes, _headers: dict[str, str], _timeout: float) -> tuple[int, bytes]:
        payload = json.loads(body.decode("utf-8"))
        answers = [{"name": "q1", "probability_true": 0.42}]
        return 200, json.dumps({"answers": answers, "latency_ms": 1}).encode("utf-8")

    response = invoke_laya_shadow_judgment(
        _binary_request(),
        decision_pack_known=lambda _a, _b: True,
        clock=lambda: 1.0,
        http_post=fake_post,
    )
    assert response.error is None
    assert response.answers is not None
    assert response.answers[0][1].probability_true == 0.42


def test_import_ai_core_does_not_load_laya() -> None:
    import sys

    assert "laya" not in sys.modules
    import ai_core  # noqa: F401

    assert "laya" not in sys.modules
    assert "torch" not in sys.modules


def test_public_api_exports_unchanged() -> None:
    import ai_core

    expected = {
        "AttributeValue",
        "PhoenixConfig",
        "init_tracing",
        "load_phoenix_config",
        "maybe_truncate",
        "record_llm_result",
        "sanitize_attributes",
        "shutdown_tracing",
        "start_llm_span",
    }
    assert set(ai_core.__all__) == expected
