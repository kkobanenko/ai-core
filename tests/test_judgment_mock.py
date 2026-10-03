"""Tests for deterministic mock judgment provider."""

from __future__ import annotations

import time

from ai_core.judgment_contracts import (
    Choice,
    DataClass,
    JudgmentErrorCategory,
    JudgmentOutcome,
    JudgmentRequest,
    JudgmentResponse,
    Noul,
    NoulReason,
    OutboundForm,
    Score,
)
from ai_core.judgment_mock import (
    DeterministicMockJudgmentProvider,
    MOCK_PROVIDER_ID,
    MockBehavior,
    MockVariant,
)
from ai_core.provider_catalog import CANONICAL_PROVIDER_IDS, NetworkBoundary


def _mock_request(**overrides: object) -> JudgmentRequest:
    values: dict = {
        "request_id": "req-1",
        "decision_pack_id": "pack-1",
        "decision_pack_version": "1",
        "criterion_id": "criterion-1",
        "allowed_choices": ("yes", "no"),
        "noul_allowed": True,
        "data_class": DataClass.SYNTHETIC,
        "outbound_form": OutboundForm.RAW,
        "network_boundary": NetworkBoundary.LOCAL_SAME_HOST,
        "request_egress_authorized": False,
        "hosted_boundary": False,
        "deadline_monotonic": 200.0,
        "provider": MOCK_PROVIDER_ID,
        "model": "mock-model",
        "model_version": "1.0.0",
        "payload": {"note": "synthetic"},
        "score_scale": None,
    }
    values.update(overrides)
    return JudgmentRequest(**values)


def test_mock_choice_variant_default() -> None:
    provider = DeterministicMockJudgmentProvider()
    req = _mock_request()
    res = provider.judge(req)
    assert res.choice == Choice("yes")
    assert res.score is None
    assert res.noul is None
    assert res.error is None
    assert res.telemetry.outcome is JudgmentOutcome.CHOICE
    assert res.telemetry.error_category is None


def test_mock_choice_custom_value_and_score() -> None:
    behavior = MockBehavior(choice_value="no", score=Score("fit", 0.8))
    provider = DeterministicMockJudgmentProvider(behavior)
    req = _mock_request()
    res = provider.judge(req)
    assert res.choice == Choice("no")
    assert res.score == Score("fit", 0.8)
    assert res.noul is None
    assert res.error is None


def test_mock_noul_variant() -> None:
    behavior = MockBehavior(variant=MockVariant.NOUL, noul_reason=NoulReason.INSUFFICIENT_EVIDENCE)
    provider = DeterministicMockJudgmentProvider(behavior)
    req = _mock_request()
    res = provider.judge(req)
    assert res.choice is None
    assert res.noul == Noul(NoulReason.INSUFFICIENT_EVIDENCE)
    assert res.error is None
    assert res.telemetry.outcome is JudgmentOutcome.NOUL


def test_mock_error_variant() -> None:
    behavior = MockBehavior(variant=MockVariant.ERROR, error_category=JudgmentErrorCategory.RATE_LIMITED)
    provider = DeterministicMockJudgmentProvider(behavior)
    req = _mock_request()
    res = provider.judge(req)
    assert res.choice is None
    assert res.noul is None
    assert res.error is JudgmentErrorCategory.RATE_LIMITED
    assert res.telemetry.outcome is JudgmentOutcome.ERROR
    assert res.telemetry.error_category is JudgmentErrorCategory.RATE_LIMITED


def test_mock_invalid_response_variant() -> None:
    behavior = MockBehavior(variant=MockVariant.INVALID_RESPONSE, invalid_provider_name="foreign_fake")
    provider = DeterministicMockJudgmentProvider(behavior)
    req = _mock_request()
    res = provider.judge(req)
    assert res.provider == "foreign_fake"
    assert res.choice == Choice("undeclared_choice_xyz")


def test_mock_timeout_variant() -> None:
    behavior = MockBehavior(variant=MockVariant.TIMEOUT, timeout_seconds=0.01)
    provider = DeterministicMockJudgmentProvider(behavior)
    req = _mock_request()
    t0 = time.monotonic()
    res = provider.judge(req)
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.009
    assert res.choice == Choice("yes")


def test_mock_not_in_canonical_catalog() -> None:
    assert MOCK_PROVIDER_ID not in CANONICAL_PROVIDER_IDS
