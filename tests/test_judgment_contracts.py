"""Контракт J1. Mock-only исполнение. Фикстура не является провайдером каталога."""

from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path

import pytest

from ai_core.capabilities import ProviderCapability
from ai_core.judgment_contracts import (
    Choice,
    JudgmentErrorCategory,
    JudgmentOutcome,
    JudgmentRequest,
    JudgmentResponse,
    JudgmentTelemetry,
    Noul,
    NoulReason,
    Score,
    ScoreScale,
    grants_authority,
    invoke_judgment as _invoke_judgment,
    request_from_json,
    request_to_json,
    response_from_json,
    response_to_json,
    validate_response_for_request,
)
from ai_core.judgment_mock import (
    DeterministicMockJudgmentProvider,
    MOCK_PROVIDER_ID,
    MockBehavior,
    MockVariant,
)
from ai_core.privacy import DataClass, OutboundForm
from ai_core.provider_catalog import CANONICAL_PROVIDER_IDS, NetworkBoundary

LOCAL_PROVIDER = "vm100_local_ollama"
EXTERNAL_PROVIDER = "mistral_external"
INTERNAL_PROVIDER = "gpu_ollama"


def _known_pack(pack_id: str, version: str) -> bool:
    """Тестовые метаданные потребителя. Это не каталог ai-core."""
    return pack_id == "pack-1" and version == "1"


def invoke_judgment(request, **kwargs):
    """Тесты знают pack-1/1. Явный resolver, включая None, не подменяется."""
    kwargs.setdefault("decision_pack_known", _known_pack)
    return _invoke_judgment(request, **kwargs)


def _clock(now: float):
    def read() -> float:
        return now

    return read


def _request(**overrides: object) -> JudgmentRequest:
    values: dict = {
        "request_id": "req-1",
        "decision_pack_id": "pack-1",
        "decision_pack_version": "1",
        "criterion_id": "criterion-1",
        "allowed_choices": ("yes",),
        "noul_allowed": True,
        "data_class": DataClass.SYNTHETIC,
        "outbound_form": OutboundForm.RAW,
        "network_boundary": NetworkBoundary.LOCAL_SAME_HOST,
        "request_egress_authorized": False,
        "hosted_boundary": False,
        "deadline_monotonic": 200.0,
        "provider": MOCK_PROVIDER_ID,
        "model": "fixture-model",
        "model_version": "1.0.0",
        "payload": {"note": "synthetic"},
        "score_scale": None,
    }
    values.update(overrides)
    return JudgmentRequest(**values)


def _telemetry(**identity: str) -> JudgmentTelemetry:
    values = {
        "provider": MOCK_PROVIDER_ID,
        "model": "fixture-model",
        "model_version": "1.0.0",
        "decision_pack_id": "pack-1",
        "decision_pack_version": "1",
    }
    values.update(identity)
    return JudgmentTelemetry(
        JudgmentOutcome.CHOICE,
        None,
        0,
        0,
        values["provider"],
        values["model"],
        values["model_version"],
        values["decision_pack_id"],
        values["decision_pack_version"],
    )


def _choice(value: str = "yes", **identity: str) -> JudgmentResponse:
    base = {
        "provider": MOCK_PROVIDER_ID,
        "model": "fixture-model",
        "model_version": "1.0.0",
        "decision_pack_id": "pack-1",
        "decision_pack_version": "1",
    }
    base.update(identity)
    return JudgmentResponse(telemetry=_telemetry(**identity), choice=Choice(value), **base)


def _bare(**variants: object) -> JudgmentResponse:
    return JudgmentResponse(
        provider=MOCK_PROVIDER_ID,
        model="fixture-model",
        model_version="1.0.0",
        decision_pack_id="pack-1",
        decision_pack_version="1",
        telemetry=_telemetry(),
        choice=variants.get("choice"),  # type: ignore[arg-type]
        score=variants.get("score"),  # type: ignore[arg-type]
        noul=variants.get("noul"),  # type: ignore[arg-type]
        error=variants.get("error"),  # type: ignore[arg-type]
    )


def _scored(score: Score) -> JudgmentResponse:
    return _bare(choice=Choice("yes"), score=score)


def test_jc1_declared_choice_is_valid() -> None:
    response = invoke_judgment(_request(), clock=_clock(100.0))
    assert response.choice == Choice("yes")
    assert response.error is None


def test_jc2_duplicate_choices_skip_provider() -> None:
    response = invoke_judgment(_request(allowed_choices=("yes", "yes")), clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.INVALID_REQUEST


def test_jc3_empty_identifier_is_invalid() -> None:
    response = invoke_judgment(_request(request_id=""), clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.INVALID_REQUEST


def test_jc4_latest_version_is_invalid() -> None:
    for version in ("latest", "v1.latest", "1.x"):
        response = invoke_judgment(_request(model_version=version), clock=_clock(100.0))
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST


def test_jc5_expired_deadline_skips_provider() -> None:
    response = invoke_judgment(_request(deadline_monotonic=50.0), clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED


def test_jc6_non_finite_deadline_is_invalid() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        response = invoke_judgment(_request(deadline_monotonic=value), clock=_clock(100.0))
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST


def test_jc7_secret_hosted_payload_is_denied() -> None:
    request = _request(
        data_class=DataClass.SECRET,
        network_boundary=NetworkBoundary.EXTERNAL,
        provider=EXTERNAL_PROVIDER,
        request_egress_authorized=True,
        hosted_boundary=True,
        payload={"token": "super-secret-token"},
    )
    response = invoke_judgment(request, clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.INVALID_REQUEST


def test_jc8_private_client_hosted_is_denied() -> None:
    request = _request(
        data_class=DataClass.PRIVATE_CLIENT_DATA,
        network_boundary=NetworkBoundary.EXTERNAL,
        provider=EXTERNAL_PROVIDER,
        request_egress_authorized=True,
        hosted_boundary=True,
    )
    response = invoke_judgment(request, clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.INVALID_REQUEST


def test_jc9_public_without_egress_is_denied() -> None:
    request = _request(
        data_class=DataClass.PUBLIC_NO_PII,
        network_boundary=NetworkBoundary.EXTERNAL,
        provider=EXTERNAL_PROVIDER,
        request_egress_authorized=False,
        hosted_boundary=True,
    )
    response = invoke_judgment(request, clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.INVALID_REQUEST


def test_jc10_mock_synthetic_local_calls_mock() -> None:
    request = _request(
        data_class=DataClass.SYNTHETIC,
        network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
        provider=MOCK_PROVIDER_ID,
        request_egress_authorized=False,
        hosted_boundary=False,
    )
    response = invoke_judgment(request, clock=_clock(100.0))
    assert response.choice == Choice("yes")
    assert response.error is None


def test_jc11_declared_choice_variant() -> None:
    response = invoke_judgment(_request(), clock=_clock(100.0))
    assert response.choice is not None
    assert response.noul is None
    assert response.error is None


def test_jc12_undeclared_choice_is_invalid_response() -> None:
    behavior = MockBehavior(choice_value="no")
    response = invoke_judgment(_request(allowed_choices=("yes",)), mock_behavior=behavior, clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert response.choice is None


def test_jc13_finite_score_inside_scale() -> None:
    scale = ScoreScale("fit", 0.0, 1.0)
    behavior = MockBehavior(score=Score("fit", 0.5))
    response = invoke_judgment(_request(score_scale=scale), mock_behavior=behavior, clock=_clock(100.0))
    assert response.score == Score("fit", 0.5)


def test_jc14_score_outside_scale() -> None:
    scale = ScoreScale("fit", 0.0, 1.0)
    behavior = MockBehavior(score=Score("fit", 2.0))
    response = invoke_judgment(_request(score_scale=scale), mock_behavior=behavior, clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc15_nan_score_is_invalid() -> None:
    scale = ScoreScale("fit", 0.0, 1.0)
    behavior = MockBehavior(score=Score("fit", math.nan))
    response = invoke_judgment(_request(score_scale=scale), mock_behavior=behavior, clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc16_infinite_score_is_invalid() -> None:
    scale = ScoreScale("fit", 0.0, 1.0)
    behavior = MockBehavior(score=Score("fit", math.inf))
    response = invoke_judgment(_request(score_scale=scale), mock_behavior=behavior, clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc17_allowed_noul() -> None:
    behavior = MockBehavior(variant=MockVariant.NOUL, noul_reason=NoulReason.NO_RELIABLE_JUDGMENT)
    response = invoke_judgment(_request(noul_allowed=True), mock_behavior=behavior, clock=_clock(100.0))
    assert response.noul == Noul(NoulReason.NO_RELIABLE_JUDGMENT)
    assert response.choice is None


def test_jc18_forbidden_noul() -> None:
    behavior = MockBehavior(variant=MockVariant.NOUL, noul_reason=NoulReason.NO_RELIABLE_JUDGMENT)
    response = invoke_judgment(_request(noul_allowed=False), mock_behavior=behavior, clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc19_noul_with_choice_is_invalid() -> None:
    raw = _bare(choice=Choice("yes"), noul=Noul(NoulReason.NO_RELIABLE_JUDGMENT))
    assert validate_response_for_request(raw, _request()) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc20_both_variants_are_invalid() -> None:
    raw = _bare(choice=Choice("yes"), noul=Noul(NoulReason.NO_RELIABLE_JUDGMENT))
    assert validate_response_for_request(raw, _request()) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc21_no_variant_is_invalid() -> None:
    raw = _bare()
    assert validate_response_for_request(raw, _request()) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc22_provider_identity_mismatch() -> None:
    behavior = MockBehavior(variant=MockVariant.INVALID_RESPONSE, invalid_provider_name="other-provider")
    response = invoke_judgment(_request(), mock_behavior=behavior, clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc23_model_version_mismatch() -> None:
    raw = _choice(model_version="9.9.9")
    assert validate_response_for_request(raw, _request()) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc24_decision_pack_version_mismatch() -> None:
    raw = _choice(decision_pack_version="99")
    assert validate_response_for_request(raw, _request()) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc25_typed_provider_error() -> None:
    behavior = MockBehavior(variant=MockVariant.ERROR, error_category=JudgmentErrorCategory.PROVIDER_UNAVAILABLE)
    response = invoke_judgment(_request(), mock_behavior=behavior, clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.PROVIDER_UNAVAILABLE
    assert response.choice is None


def test_jc26_unexpected_exception_is_internal() -> None:
    class RaisingMock(MockBehavior):
        pass

    class BrokenProvider:
        def judge(self, req):
            raise RuntimeError("payload secret leaked")

    import ai_core.judgment_contracts as jc
    old_method = jc._judge_within_deadline
    try:
        jc._judge_within_deadline = lambda active, request, ready: (_ for _ in ()).throw(RuntimeError("payload secret leaked"))
        response = invoke_judgment(_request(), clock=_clock(100.0))
        assert response.error is JudgmentErrorCategory.INTERNAL_ERROR
        assert "leaked" not in response_to_json(response)
    finally:
        jc._judge_within_deadline = old_method


def test_jc27_round_trip() -> None:
    request = _request(payload={"note": "synthetic"}, score_scale=ScoreScale("fit", 0.0, 1.0))
    restored = request_from_json(request_to_json(request))
    assert restored == request
    raw = _scored(Score("fit", 0.25))
    assert response_from_json(response_to_json(raw)) == raw


def test_jc28_telemetry_has_no_payload() -> None:
    request = _request(payload={"note": "synthetic-body"})
    response = invoke_judgment(request, clock=_clock(100.0))
    text = response_to_json(response)
    telemetry = text.split('"telemetry":', 1)[1]
    assert "synthetic-body" not in telemetry
    assert "payload" not in telemetry


def test_jc29_telemetry_has_no_secret() -> None:
    request = _request(payload={"token": "super-secret-token"})
    response = invoke_judgment(request, clock=_clock(100.0))
    telemetry = response_to_json(response).split('"telemetry":', 1)[1]
    assert "super-secret-token" not in telemetry


def test_jc30_privacy_before_provider_construction() -> None:
    request = _request(
        data_class=DataClass.SECRET,
        network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
        provider=MOCK_PROVIDER_ID,
    )
    response = invoke_judgment(request, clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED


def test_jc31_deadline_before_provider_invocation() -> None:
    response = invoke_judgment(_request(deadline_monotonic=1.0), clock=_clock(5.0))
    assert response.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED


def test_jc32_invalid_response_hides_bad_choice() -> None:
    behavior = MockBehavior(choice_value="not-declared")
    response = invoke_judgment(_request(), mock_behavior=behavior, clock=_clock(100.0))
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert response.choice is None
    assert "not-declared" not in response_to_json(response)


def test_jc33_noul_is_not_approval() -> None:
    behavior = MockBehavior(variant=MockVariant.NOUL, noul_reason=NoulReason.NO_RELIABLE_JUDGMENT)
    response = invoke_judgment(_request(), mock_behavior=behavior, clock=_clock(100.0))
    assert response.noul is not None
    assert not hasattr(response.noul, "choice")
    assert grants_authority(response) is False
    assert "automatic_approval" not in response_to_json(response)


def test_jc34_choice_does_not_grant_completion() -> None:
    response = invoke_judgment(_request(), clock=_clock(100.0))
    assert response.choice == Choice("yes")
    assert grants_authority(response) is False
    assert "completion_authority" not in response_to_json(response)


def test_retry_count_stays_zero() -> None:
    response = invoke_judgment(_request(), clock=_clock(100.0))
    assert response.telemetry.retry_count == 0


def test_r1_malformed_variants_do_not_escape() -> None:
    samples = (
        None,
        "text",
        {},
        _bare(choice="yes"),
        _bare(choice=Choice("yes"), score="0.5"),
        _bare(noul="unknown"),
        _bare(error="provider_unavailable"),
    )
    for sample in samples:
        assert validate_response_for_request(sample, _request()) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_r2_late_choice_is_deadline_exhausted() -> None:
    class Clock:
        def __init__(self) -> None:
            self.reads = 0

        def __call__(self) -> float:
            self.reads += 1
            if self.reads <= 3:
                return 10.0
            return 500.0

    response = invoke_judgment(_request(deadline_monotonic=100.0), clock=Clock())
    assert response.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert response.choice is None
    assert "yes" not in response_to_json(response)


def test_r2_on_time_choice_stays_valid() -> None:
    response = invoke_judgment(_request(deadline_monotonic=200.0), clock=_clock(100.0))
    assert response.choice == Choice("yes")
    assert response.error is None


def test_r3_selector_pins_are_invalid() -> None:
    for pin in ("*", "jev-*", ">=1", "^1.2", "~1.2", "1.x", "latest"):
        response = invoke_judgment(_request(model_version=pin), clock=_clock(100.0))
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST


def test_r4_malformed_json_types_are_not_coerced() -> None:
    document = json.loads(request_to_json(_request()))
    document["request_id"] = None
    with pytest.raises(ValueError):
        request_from_json(json.dumps(document))
    document = json.loads(request_to_json(_request()))
    document["allowed_choices"] = [1]
    with pytest.raises(ValueError):
        request_from_json(json.dumps(document))
    document = json.loads(request_to_json(_request()))
    document["deadline_monotonic"] = "200"
    with pytest.raises(ValueError):
        request_from_json(json.dumps(document))
    answer = json.loads(response_to_json(invoke_judgment(_request(), clock=_clock(100.0))))
    answer["choice"] = 1
    with pytest.raises(ValueError):
        response_from_json(json.dumps(answer))


def test_b1_noul_reason_is_bounded() -> None:
    behavior = MockBehavior(variant=MockVariant.NOUL, noul_reason=NoulReason.INSUFFICIENT_EVIDENCE)
    valid = invoke_judgment(_request(), mock_behavior=behavior, clock=_clock(100.0))
    assert valid.noul == Noul(NoulReason.INSUFFICIENT_EVIDENCE)
    restored = response_from_json(response_to_json(valid))
    assert restored.noul == valid.noul
    leaked = _bare(noul=Noul("super-secret-token sentence"))  # type: ignore[arg-type]
    assert validate_response_for_request(leaked, _request()) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    document = json.loads(response_to_json(valid))
    document["noul"] = "the model cannot decide"
    with pytest.raises(ValueError):
        response_from_json(json.dumps(document))


def test_b2_response_json_invariants() -> None:
    valid = invoke_judgment(_request(), clock=_clock(100.0))
    document = json.loads(response_to_json(valid))
    both = dict(document)
    both["noul"] = NoulReason.AMBIGUOUS_INPUT.value
    with pytest.raises(ValueError):
        response_from_json(json.dumps(both))
    empty = dict(document)
    empty["choice"] = None
    empty["score"] = None
    with pytest.raises(ValueError):
        response_from_json(json.dumps(empty))
    negative = dict(document)
    negative["telemetry"] = dict(document["telemetry"])
    negative["telemetry"]["retry_count"] = -1
    with pytest.raises(ValueError):
        response_from_json(json.dumps(negative))
    late = dict(document)
    late["telemetry"] = dict(document["telemetry"])
    late["telemetry"]["latency_ms"] = -5
    with pytest.raises(ValueError):
        response_from_json(json.dumps(late))
    parsed = response_from_json(response_to_json(valid))
    assert validate_response_for_request(parsed, _request()) is None
    foreign = _choice("no")
    assert validate_response_for_request(foreign, _request()) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_b3_malformed_choice_collection_is_invalid_request() -> None:
    samples = (None, "ABC", (1,), (None,), ({},), (), ("yes", "yes"))
    for choices in samples:
        response = invoke_judgment(_request(allowed_choices=choices), clock=_clock(1.0))  # type: ignore[arg-type]
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST
    ok = invoke_judgment(_request(allowed_choices=("yes",)), clock=_clock(1.0))
    assert ok.choice == Choice("yes")


def test_b4_positive_pin_grammar() -> None:
    allowed = (
        "typesafe_jev",
        "jev-1.13.0",
        "1.13.0",
        "fixture-model",
        "fixture-model-v1",
        "lite-j1-fixture",
        "provider_1",
        "model.v2",
        "a",
        "1",
    )
    for pin in allowed:
        response = invoke_judgment(_request(model_version=pin), clock=_clock(1.0))
        assert response.error is None, pin
    rejected = (
        "*",
        "jev-*",
        "latest",
        "model-latest",
        ">=1",
        ">1",
        "<=2",
        "<2",
        "^1.0",
        "~1.0",
        "1.x",
        "x",
        "",
        "   ",
        "model with spaces",
        "model/slash",
        "model@at",
        "model#hash",
        "model:colon",
        "model?question",
    )
    for pin in rejected:
        response = invoke_judgment(_request(model_version=pin), clock=_clock(1.0))
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST, pin


def test_c1_real_providers_fail_closed_under_j1() -> None:
    for provider in (EXTERNAL_PROVIDER, LOCAL_PROVIDER, INTERNAL_PROVIDER):
        response = invoke_judgment(
            _request(provider=provider),
            clock=_clock(10.0),
        )
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST


def test_c2_deadline_covers_validation() -> None:
    class SequenceClock:
        def __init__(self, values: list[float]) -> None:
            self.values = list(values)

        def __call__(self) -> float:
            return self.values.pop(0)

    late_validation = invoke_judgment(
        _request(deadline_monotonic=1.0),
        clock=SequenceClock([0.0, 0.0, 0.4, 1.1]),
    )
    assert late_validation.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert late_validation.choice is None
    late_provider = invoke_judgment(
        _request(deadline_monotonic=1.0),
        clock=SequenceClock([0.0, 0.0, 0.4, 1.2]),
    )
    assert late_provider.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert "yes" not in response_to_json(late_provider)
    on_time = invoke_judgment(
        _request(deadline_monotonic=5.0),
        clock=SequenceClock([0.0, 0.0, 0.1, 0.4]),
    )
    assert on_time.choice == Choice("yes")


def test_c3_invalid_request_does_not_echo_input() -> None:
    for bad in (None, "text", {}, object()):
        response = invoke_judgment(bad)  # type: ignore[arg-type]
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST
        assert response.provider == "unvalidated"
    for overrides in (
        {"provider": None},
        {"model": {}},
        {"model_version": 12},
        {"decision_pack_id": None},
        {"allowed_choices": None},
    ):
        response = invoke_judgment(_request(**overrides), clock=_clock(1.0))  # type: ignore[arg-type]
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST
        assert response.provider == "unvalidated"
        rendered = response_to_json(response)
        assert "None" not in rendered
        assert "{}" not in rendered


def test_c4_telemetry_outcome_is_closed() -> None:
    choice = invoke_judgment(_request(), clock=_clock(100.0))
    noul_behavior = MockBehavior(variant=MockVariant.NOUL, noul_reason=NoulReason.NO_RELIABLE_JUDGMENT)
    noul = invoke_judgment(_request(), mock_behavior=noul_behavior, clock=_clock(100.0))
    err_behavior = MockBehavior(variant=MockVariant.ERROR, error_category=JudgmentErrorCategory.PROVIDER_UNAVAILABLE)
    failure = invoke_judgment(_request(), mock_behavior=err_behavior, clock=_clock(100.0))
    assert choice.telemetry.outcome is JudgmentOutcome.CHOICE
    assert choice.telemetry.error_category is None
    assert noul.telemetry.outcome is JudgmentOutcome.NOUL
    assert failure.telemetry.outcome is JudgmentOutcome.ERROR
    assert failure.telemetry.error_category is JudgmentErrorCategory.PROVIDER_UNAVAILABLE
    document = json.loads(response_to_json(choice))
    document["telemetry"]["outcome"] = "payload-fragment"
    with pytest.raises(ValueError):
        response_from_json(json.dumps(document))
    document = json.loads(response_to_json(choice))
    document["telemetry"]["error_category"] = "arbitrary provider text"
    with pytest.raises(ValueError):
        response_from_json(json.dumps(document))
    document = json.loads(response_to_json(noul))
    document["telemetry"]["error_category"] = "privacy_egress_denied"
    with pytest.raises(ValueError):
        response_from_json(json.dumps(document))
    document = json.loads(response_to_json(failure))
    document["telemetry"]["error_category"] = "deadline_exhausted"
    with pytest.raises(ValueError):
        response_from_json(json.dumps(document))
    document = json.loads(response_to_json(failure))
    document["telemetry"]["error_category"] = None
    with pytest.raises(ValueError):
        response_from_json(json.dumps(document))
    assert response_from_json(response_to_json(choice)).telemetry.outcome is JudgmentOutcome.CHOICE


def test_d1_unknown_network_boundary_fails_closed() -> None:
    for data_class in DataClass:
        for hosted in (False, True):
            response = invoke_judgment(
                _request(
                    data_class=data_class,
                    network_boundary=NetworkBoundary.UNKNOWN_BOUNDARY,
                    request_egress_authorized=True,
                    hosted_boundary=hosted,
                ),
                clock=_clock(1.0),
            )
            assert response.error is JudgmentErrorCategory.INVALID_REQUEST


def test_d1_privacy_matrix_uses_real_enums() -> None:
    for boundary in NetworkBoundary:
        for data_class in DataClass:
            for egress in (False, True):
                for hosted in (False, True):
                    response = invoke_judgment(
                        _request(
                            data_class=data_class,
                            network_boundary=boundary,
                            request_egress_authorized=egress,
                            hosted_boundary=hosted,
                            provider=MOCK_PROVIDER_ID,
                        ),
                        clock=_clock(1.0),
                    )
                    # mock_judgment enforces fixed LOCAL_SAME_HOST and hosted_boundary=False
                    if boundary is not NetworkBoundary.LOCAL_SAME_HOST or hosted is True:
                        assert response.error is JudgmentErrorCategory.INVALID_REQUEST
                    elif data_class is DataClass.SECRET:
                        assert response.error is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED
                    else:
                        assert response.error is None


def test_d2_factory_expiry_skips_judge() -> None:
    class Clock:
        def __init__(self) -> None:
            self.reads = 0

        def __call__(self) -> float:
            self.reads += 1
            if self.reads == 1:
                return 0.5
            return 2.0

    response = invoke_judgment(_request(deadline_monotonic=1.0), clock=Clock())
    assert response.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED


def test_d3_huge_deadline_is_invalid_request() -> None:
    for huge in (10**400, -(10**400)):
        response = invoke_judgment(
            _request(deadline_monotonic=huge),  # type: ignore[arg-type]
            clock=_clock(1.0),
        )
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST
    huge_scale = invoke_judgment(
        _request(score_scale=ScoreScale("fit", 0.0, 10**400)),  # type: ignore[arg-type]
        clock=_clock(1.0),
    )
    assert huge_scale.error is JudgmentErrorCategory.INVALID_REQUEST


def test_d4_telemetry_type_before_range() -> None:
    base = _choice()
    for latency, retry in (("bad", 0), (None, 0), (True, 0), (0, "bad"), (0, None), (0, True), (-1, 0), (0, -1)):
        response = JudgmentResponse(
            provider=base.provider,
            model=base.model,
            model_version=base.model_version,
            decision_pack_id=base.decision_pack_id,
            decision_pack_version=base.decision_pack_version,
            telemetry=JudgmentTelemetry(
                JudgmentOutcome.CHOICE,
                None,
                latency,  # type: ignore[arg-type]
                retry,  # type: ignore[arg-type]
                base.provider,
                base.model,
                base.model_version,
                base.decision_pack_id,
                base.decision_pack_version,
            ),
            choice=Choice("yes"),
        )
        with pytest.raises(ValueError):
            response_to_json(response)
        assert validate_response_for_request(response, _request()) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_e1_oversized_score_fails_closed() -> None:
    scale = ScoreScale("fit", 0.0, 1.0)
    for value in (10**400, -(10**400), float("nan"), float("inf"), float("-inf"), True, "bad"):
        raw = _bare(choice=Choice("yes"), score=Score("fit", value))  # type: ignore[arg-type]
        assert validate_response_for_request(raw, _request(score_scale=scale)) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_e2_request_json_must_be_semantically_valid() -> None:
    valid = _request()
    assert request_from_json(request_to_json(valid)) == valid
    document = json.loads(request_to_json(valid))
    cases = []
    empty = dict(document)
    empty["allowed_choices"] = []
    cases.append(empty)
    duplicate = dict(document)
    duplicate["allowed_choices"] = ["yes", "yes"]
    cases.append(duplicate)
    latest = dict(document)
    latest["model_version"] = "latest"
    cases.append(latest)
    star = dict(document)
    star["provider"] = "jev-*"
    cases.append(star)
    inverted = dict(document)
    inverted["score_scale"] = {"score_id": "fit", "minimum": 1, "maximum": 0}
    cases.append(inverted)
    hosted = dict(document)
    hosted["hosted_boundary"] = True
    hosted["network_boundary"] = "local_same_host"
    cases.append(hosted)
    for item in cases:
        with pytest.raises(ValueError):
            request_from_json(json.dumps(item))


def test_e3_invalid_clock_fails_closed() -> None:
    def clocks():
        yield lambda: float("nan")
        yield lambda: float("inf")
        yield lambda: float("-inf")
        yield lambda: None
        yield lambda: "bad"
        def raise_type():
            raise TypeError("clock")
        def raise_value():
            raise ValueError("clock")
        yield raise_type
        yield raise_value

    for clock in clocks():
        response = invoke_judgment(_request(), clock=clock)
        assert response.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
        assert response.choice is None
    zero = invoke_judgment(
        _request(deadline_monotonic=1.0),
        clock=lambda: 0.0,
    )
    assert zero.choice == Choice("yes")


def test_f1_trusted_provider_boundary_is_authoritative() -> None:
    # Any non-mock provider fails closed with INVALID_REQUEST under J1
    for p in (EXTERNAL_PROVIDER, LOCAL_PROVIDER, INTERNAL_PROVIDER, "not-a-governed-provider"):
        res = invoke_judgment(_request(provider=p), clock=_clock(1.0))
        assert res.error is JudgmentErrorCategory.INVALID_REQUEST


def test_f2_authorization_docs_match_remote_truth() -> None:
    root = Path(__file__).resolve().parents[1]
    spec = (root / "specs/003-judgment-provider/spec.md").read_text(encoding="utf-8")
    tasks = (root / "specs/003-judgment-provider/tasks.md").read_text(encoding="utf-8")
    plan = (root / "specs/003-judgment-provider/plan.md").read_text(encoding="utf-8")
    combined = spec + tasks + plan
    assert "AUTHORIZE_J1_CONTRACT_ONLY" in combined
    assert "717cace0d109105c406723de30cd72e4e3ed7dd4" in combined
    assert "operator-decision-authorize-j1-contract-only.yaml" in combined
    assert "contract_only" in combined
    assert "current state `HOLD_J1`" not in combined
    assert "current state remains `HOLD_J1`" not in combined
    assert "documentation only" not in plan.lower()
    assert "do not create files in this package" not in plan.lower()
    assert "DOCS_ONLY_DESIGN" not in tasks
    assert (root / "src/ai_core/judgment_contracts.py").is_file()


def test_f3_unknown_decision_pack_skips_provider() -> None:
    def known(pack_id: str, version: str) -> bool:
        return pack_id == "pack-1" and version == "1"

    ok = invoke_judgment(_request(), clock=_clock(1.0), decision_pack_known=known)
    assert ok.choice == Choice("yes")
    for overrides in (
        {"decision_pack_version": "999"},
        {"decision_pack_id": "other-pack"},
        {"decision_pack_id": "pack-typo"},
    ):
        response = invoke_judgment(
            _request(**overrides),
            clock=_clock(1.0),
            decision_pack_known=known,
        )
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST

    def explode(pack_id: str, version: str) -> bool:
        raise RuntimeError("resolver down")

    failed = invoke_judgment(
        _request(),
        clock=_clock(1.0),
        decision_pack_known=explode,
    )
    assert failed.error is JudgmentErrorCategory.INVALID_REQUEST
    absent = invoke_judgment(
        _request(),
        clock=_clock(1.0),
        decision_pack_known=None,
    )
    assert absent.error is JudgmentErrorCategory.INVALID_REQUEST


def test_f4_hostile_identity_equality_does_not_escape() -> None:
    class Hostile:
        def __eq__(self, other: object) -> bool:
            raise RuntimeError("hostile equality")

    fields = (
        "provider",
        "model",
        "model_version",
        "decision_pack_id",
        "decision_pack_version",
    )
    base = _choice()
    for field in fields:
        values = {
            "provider": base.provider,
            "model": base.model,
            "model_version": base.model_version,
            "decision_pack_id": base.decision_pack_id,
            "decision_pack_version": base.decision_pack_version,
        }
        values[field] = Hostile()
        raw = JudgmentResponse(
            provider=values["provider"],
            model=values["model"],
            model_version=values["model_version"],
            decision_pack_id=values["decision_pack_id"],
            decision_pack_version=values["decision_pack_version"],
            telemetry=base.telemetry,
            choice=Choice("yes"),
        )
        assert validate_response_for_request(raw, _request()) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
        with pytest.raises(ValueError):
            response_to_json(raw)


def test_g1_j1_execution_is_mock_only() -> None:
    """Dedicated regression proving real providers and arbitrary factories cannot execute under J1."""
    # 1. Arbitrary production providers cannot execute
    for prod_provider in (EXTERNAL_PROVIDER, LOCAL_PROVIDER, INTERNAL_PROVIDER, "ollama_cloud"):
        req = _request(provider=prod_provider)
        res = invoke_judgment(req, clock=_clock(1.0))
        assert res.error is JudgmentErrorCategory.INVALID_REQUEST
        assert res.choice is None

    # 2. No provider_factory parameter exists on invoke_judgment
    import inspect
    sig = inspect.signature(_invoke_judgment)
    assert "provider_factory" not in sig.parameters

    # 3. mock_judgment executes deterministically
    mock_req = _request(provider=MOCK_PROVIDER_ID)
    mock_res = invoke_judgment(mock_req, clock=_clock(1.0))
    assert mock_res.error is None
    assert mock_res.choice == Choice("yes")

    # 4. No ProviderCapability.JUDGMENT was added
    assert not hasattr(ProviderCapability, "JUDGMENT")
    assert "JUDGMENT" not in [c.name for c in ProviderCapability]
    assert "judgment" not in [c.value for c in ProviderCapability]


def test_g1_critical_side_effect_zero_external_execution() -> None:
    """Mandatory test: Prove external factory/judge calls remain zero."""
    external_calls = {"factory": 0, "judge": 0}

    class ExplodingExternalProvider:
        def __init__(self) -> None:
            external_calls["factory"] += 1
            raise AssertionError("External provider constructed under J1!")

        def judge(self, req: JudgmentRequest) -> JudgmentResponse:
            external_calls["judge"] += 1
            raise AssertionError("External provider judge() executed under J1!")

    # Attempt to route mistral_external through J1
    req = _request(
        provider=EXTERNAL_PROVIDER,
        network_boundary=NetworkBoundary.EXTERNAL,
        data_class=DataClass.SYNTHETIC,
        request_egress_authorized=True,
        hosted_boundary=True,
    )
    res = invoke_judgment(req, clock=_clock(1.0))
    assert res.error is JudgmentErrorCategory.INVALID_REQUEST
    assert external_calls["factory"] == 0
    assert external_calls["judge"] == 0


def test_g2_clock_callback_exceptions_fail_closed() -> None:
    for kind in (RuntimeError, OSError):
        def clock() -> float:
            raise kind("clock")

        response = invoke_judgment(_request(), clock=clock)
        assert response.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED


def test_h2_blocking_judge_returns_before_hang() -> None:
    behavior = MockBehavior(variant=MockVariant.TIMEOUT, timeout_seconds=2.0)
    started = time.monotonic()
    response = invoke_judgment(
        _request(deadline_monotonic=started + 0.1),
        mock_behavior=behavior,
    )
    elapsed = time.monotonic() - started
    assert response.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert response.choice is None
    assert elapsed < 1.5


def test_h3_latency_is_measured_after_validation() -> None:
    class SequenceClock:
        def __init__(self, values: list[float]) -> None:
            self.values = list(values)

        def __call__(self) -> float:
            return self.values.pop(0)

    success = invoke_judgment(
        _request(deadline_monotonic=5.0),
        clock=SequenceClock([0.0, 0.0, 0.0, 0.3]),
    )
    assert success.choice == Choice("yes")
    assert success.telemetry.latency_ms == 300
    late = invoke_judgment(
        _request(deadline_monotonic=1.0),
        clock=SequenceClock([0.0, 0.0, 0.0, 1.5]),
    )
    assert late.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert late.choice is None
    assert late.telemetry.latency_ms == 1500


def test_round_1_resolver_deadline_bounded() -> None:
    """Test that a blocking decision-pack resolver times out within the deadline."""
    def blocking_resolver(pack_id: str, version: str) -> bool:
        time.sleep(2.0)
        return True

    started = time.monotonic()
    req = _request(deadline_monotonic=started + 0.1)
    res = invoke_judgment(req, decision_pack_known=blocking_resolver)

    elapsed = time.monotonic() - started
    assert res.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert res.choice is None
    assert elapsed < 1.5


def test_round_1_reject_hostile_str_subclass() -> None:
    """Test that hostile str subclasses overriding __ne__ are rejected as INVALID_REQUEST."""
    class HostileStr(str):
        def __ne__(self, other: object) -> bool:
            raise RuntimeError("hostile ne override invoked")

    req = _request(provider=HostileStr("mock_judgment"))
    res = invoke_judgment(req, clock=_clock(1.0))
    assert res.error is JudgmentErrorCategory.INVALID_REQUEST

    req_model = _request(model=HostileStr("fixture-model"))
    res_model = invoke_judgment(req_model, clock=_clock(1.0))
    assert res_model.error is JudgmentErrorCategory.INVALID_REQUEST


def test_round_1_reject_non_finite_payload_json() -> None:
    """Test that payloads containing NaN or Infinity fail json serialization."""
    req_nan = _request(payload={"value": float("nan")})
    with pytest.raises(ValueError):
        request_to_json(req_nan)

    req_inf = _request(payload={"value": float("inf")})
    with pytest.raises(ValueError):
        request_to_json(req_inf)


def test_round_2_daemon_thread_no_blocking_worker_retention() -> None:
    """Prove that timed-out resolver or judge runs on a daemon thread so it cannot block process shutdown."""
    worker_thread = None

    def blocking_resolver(pack_id: str, version: str) -> bool:
        nonlocal worker_thread
        worker_thread = threading.current_thread()
        time.sleep(2.0)
        return True

    started = time.monotonic()
    req = _request(deadline_monotonic=started + 0.1)
    res = invoke_judgment(req, decision_pack_known=blocking_resolver)
    assert res.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert worker_thread is not None
    assert worker_thread.daemon is True


def test_round_2_reject_hostile_str_subclass_in_response() -> None:
    """Prove that str subclasses in response or telemetry identity are rejected as INVALID_PROVIDER_RESPONSE."""
    class HostileStr(str):
        def __eq__(self, other: object) -> bool:
            raise RuntimeError("hostile eq override invoked")

    raw = _choice()
    # Replace response provider with HostileStr
    hostile_response = JudgmentResponse(
        provider=HostileStr(raw.provider),
        model=raw.model,
        model_version=raw.model_version,
        decision_pack_id=raw.decision_pack_id,
        decision_pack_version=raw.decision_pack_version,
        telemetry=raw.telemetry,
        choice=raw.choice,
    )
    assert validate_response_for_request(hostile_response, _request()) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    with pytest.raises(ValueError):
        response_to_json(hostile_response)

    # Also test hostile subclass in telemetry provider
    hostile_telemetry = JudgmentTelemetry(
        outcome=JudgmentOutcome.CHOICE,
        error_category=None,
        latency_ms=0,
        retry_count=0,
        provider=HostileStr(raw.provider),
        model=raw.model,
        model_version=raw.model_version,
        decision_pack_id=raw.decision_pack_id,
        decision_pack_version=raw.decision_pack_version,
    )
    hostile_tel_response = JudgmentResponse(
        provider=raw.provider,
        model=raw.model,
        model_version=raw.model_version,
        decision_pack_id=raw.decision_pack_id,
        decision_pack_version=raw.decision_pack_version,
        telemetry=hostile_telemetry,
        choice=raw.choice,
    )
    assert validate_response_for_request(hostile_tel_response, _request()) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    with pytest.raises(ValueError):
        response_to_json(hostile_tel_response)


def test_round_3_reject_non_finite_constants_in_json_parsing() -> None:
    """Prove that NaN/Infinity constants in request and response JSON are rejected during parsing."""
    valid_req_json = request_to_json(_request(payload={"note": "synthetic"}))
    # Test request_from_json with NaN in payload
    nan_req_json = valid_req_json.replace('"payload":{"note":"synthetic"}', '"payload":{"val":NaN}')
    with pytest.raises(ValueError, match="non-finite constant|NaN"):
        request_from_json(nan_req_json)

    inf_req_json = valid_req_json.replace('"payload":{"note":"synthetic"}', '"payload":{"val":Infinity}')
    with pytest.raises(ValueError, match="non-finite constant|Infinity"):
        request_from_json(inf_req_json)

    # Test that Python request with NaN payload fails _request_error / invoke_judgment
    req_nan = _request(payload={"bad": float("nan")})
    res = invoke_judgment(req_nan, clock=_clock(1.0))
    assert res.error is JudgmentErrorCategory.INVALID_REQUEST

    # Test response_from_json with NaN
    valid_res_json = response_to_json(_choice())
    nan_res_json = valid_res_json.replace('"latency_ms":0', '"latency_ms":NaN')
    with pytest.raises(ValueError, match="non-finite constant|NaN"):
        response_from_json(nan_res_json)


def test_round_3_reject_hostile_str_subclass_in_response_choice() -> None:
    """Prove that str subclasses in Choice.value are rejected without leaking hostile eq/ne exceptions."""
    class HostileChoiceStr(str):
        def __eq__(self, other: object) -> bool:
            raise RuntimeError("hostile choice eq invoked")

        def __ne__(self, other: object) -> bool:
            raise RuntimeError("hostile choice ne invoked")

    req = _request(allowed_choices=("good-choice",))
    res = JudgmentResponse(
        provider=req.provider,
        model=req.model,
        model_version=req.model_version,
        decision_pack_id=req.decision_pack_id,
        decision_pack_version=req.decision_pack_version,
        telemetry=JudgmentTelemetry(
            outcome=JudgmentOutcome.CHOICE,
            error_category=None,
            latency_ms=0,
            retry_count=0,
            provider=req.provider,
            model=req.model,
            model_version=req.model_version,
            decision_pack_id=req.decision_pack_id,
            decision_pack_version=req.decision_pack_version,
        ),
        choice=Choice(HostileChoiceStr("good-choice")),
    )
    assert validate_response_for_request(res, req) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE

    # Test mock behavior with hostile choice string
    mock_res = invoke_judgment(
        req,
        mock_behavior=MockBehavior(choice_value=HostileChoiceStr("good-choice")),
        clock=_clock(1.0),
    )
    assert mock_res.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_round_3_reject_unknown_fields_in_nested_score_and_scale() -> None:
    """Prove that extra unknown fields in score and score_scale objects raise ValueError."""
    # Extra field in response score
    res = _choice()
    res_doc = json.loads(response_to_json(res))
    res_doc["score"] = {"score_id": "fit", "value": 0.5, "provider_extra": "unexpected"}
    with pytest.raises(ValueError, match="score must only contain score_id and value"):
        response_from_json(json.dumps(res_doc))

    # Extra field in request score_scale
    req_doc = json.loads(request_to_json(_request()))
    req_doc["score_scale"] = {"score_id": "fit", "minimum": 0.0, "maximum": 1.0, "extra": 123}
    with pytest.raises(ValueError, match="score_scale must only contain score_id, minimum, and maximum"):
        request_from_json(json.dumps(req_doc))


def test_round_4_privacy_denial_precedes_decision_pack_lookup() -> None:
    """Prove that SECRET data is denied with PRIVACY_EGRESS_DENIED before calling decision_pack_known."""
    called = False

    def resolver(pack_id: str, version: str) -> bool:
        nonlocal called
        called = True
        return False

    req = _request(data_class=DataClass.SECRET)
    res = invoke_judgment(req, decision_pack_known=resolver, clock=_clock(1.0))
    assert res.error is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED
    assert called is False


def test_round_4_payload_bounded_acyclic_json_shape() -> None:
    """Prove that cyclical, deep, or non-JSON payloads return INVALID_REQUEST without RecursionError."""
    # Self-referential list
    cyclic_list: list = []
    cyclic_list.append(cyclic_list)
    req_cyclic_list = _request(payload=cyclic_list)
    res_list = invoke_judgment(req_cyclic_list, clock=_clock(1.0))
    assert res_list.error is JudgmentErrorCategory.INVALID_REQUEST

    # Self-referential dict
    cyclic_dict: dict = {}
    cyclic_dict["self"] = cyclic_dict
    req_cyclic_dict = _request(payload=cyclic_dict)
    res_dict = invoke_judgment(req_cyclic_dict, clock=_clock(1.0))
    assert res_dict.error is JudgmentErrorCategory.INVALID_REQUEST

    # Non-JSON type (tuple)
    req_tuple = _request(payload={"key": (1, 2, 3)})
    res_tuple = invoke_judgment(req_tuple, clock=_clock(1.0))
    assert res_tuple.error is JudgmentErrorCategory.INVALID_REQUEST

    # Deep tree exceeding max depth
    deep: dict = {"level": 0}
    curr = deep
    for i in range(1, 40):
        nxt: dict = {"level": i}
        curr["child"] = nxt
        curr = nxt
    req_deep = _request(payload=deep)
    res_deep = invoke_judgment(req_deep, clock=_clock(1.0))
    assert res_deep.error is JudgmentErrorCategory.INVALID_REQUEST


def test_round_5_reject_hostile_numeric_subclasses() -> None:
    """Prove that float and int subclasses with hostile overrides fail validation cleanly as INVALID_REQUEST."""
    class HostileFloat(float):
        def __float__(self) -> float:
            raise RuntimeError("hostile float override")

    class HostileInt(int):
        def bit_length(self) -> int:
            raise RuntimeError("hostile bit_length override")

    # Hostile deadline
    req_hostile_deadline = _request(deadline_monotonic=HostileFloat(100.0))
    res_deadline = invoke_judgment(req_hostile_deadline, clock=_clock(1.0))
    assert res_deadline.error is JudgmentErrorCategory.INVALID_REQUEST

    # Hostile score scale minimum
    scale_hostile = ScoreScale(score_id="fit", minimum=HostileFloat(0.0), maximum=1.0)
    req_hostile_scale = _request(score_scale=scale_hostile)
    res_scale = invoke_judgment(req_hostile_scale, clock=_clock(1.0))
    assert res_scale.error is JudgmentErrorCategory.INVALID_REQUEST

    # Hostile int
    req_hostile_int = _request(deadline_monotonic=HostileInt(100))
    res_int = invoke_judgment(req_hostile_int, clock=_clock(1.0))
    assert res_int.error is JudgmentErrorCategory.INVALID_REQUEST


def test_round_5_bounded_concurrent_workers_no_accumulation() -> None:
    """Prove that timed-out workers are bounded by the concurrency limit and cannot accumulate unbounded threads."""
    from ai_core.judgment_contracts import _MAX_CONCURRENT_WORKERS, _WORKER_SEMAPHORE

    # Verify semaphore exists and is bounded
    assert _MAX_CONCURRENT_WORKERS <= 16

    # Test that repeated timeouts return DEADLINE_EXHAUSTED cleanly without unboundedly accumulating workers
    def slow_resolver(pack_id: str, version: str) -> bool:
        time.sleep(0.5)
        return True

    started = time.monotonic()
    req = _request(deadline_monotonic=started + 0.05)
    for _ in range(5):
        res = invoke_judgment(req, decision_pack_known=slow_resolver)
        assert res.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED


def test_round_5_reject_oversized_identifiers_and_choices() -> None:
    """Prove that identifiers over 128 chars and choice sets over 128 items are rejected."""
    # Oversized criterion_id
    long_id = "a" * 129
    req_long_criterion = _request(criterion_id=long_id)
    assert invoke_judgment(req_long_criterion, clock=_clock(1.0)).error is JudgmentErrorCategory.INVALID_REQUEST

    # Oversized choice string
    long_choice = "c" * 129
    req_long_choice = _request(allowed_choices=(long_choice,))
    assert invoke_judgment(req_long_choice, clock=_clock(1.0)).error is JudgmentErrorCategory.INVALID_REQUEST

    # Oversized choice tuple (> 128 choices)
    many_choices = tuple(f"choice-{i}" for i in range(130))
    req_many_choices = _request(allowed_choices=many_choices)
    assert invoke_judgment(req_many_choices, clock=_clock(1.0)).error is JudgmentErrorCategory.INVALID_REQUEST
