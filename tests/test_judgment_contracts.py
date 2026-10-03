"""Контракт J1. Фикстура не является провайдером каталога."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

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
from ai_core.privacy import DataClass, OutboundForm
from ai_core.provider_catalog import NetworkBoundary

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


class SpyProvider:
    """Тестовый провайдер. В каталог не входит."""

    def __init__(self, result: object) -> None:
        self.result = result
        self.calls = 0
        self.built = 0

    def factory(self) -> "SpyProvider":
        self.built += 1
        return self

    def judge(self, request: JudgmentRequest) -> JudgmentResponse:
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result  # type: ignore[return-value]


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
        "provider": LOCAL_PROVIDER,
        "model": "fixture-model",
        "model_version": "1.0.0",
        "payload": {"note": "synthetic"},
        "score_scale": None,
    }
    values.update(overrides)
    return JudgmentRequest(**values)


def _telemetry(**identity: str) -> JudgmentTelemetry:
    values = {
        "provider": LOCAL_PROVIDER,
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
        "provider": LOCAL_PROVIDER,
        "model": "fixture-model",
        "model_version": "1.0.0",
        "decision_pack_id": "pack-1",
        "decision_pack_version": "1",
    }
    base.update(identity)
    return JudgmentResponse(telemetry=_telemetry(**identity), choice=Choice(value), **base)


def _invoke(request: JudgmentRequest, result: object, now: float = 100.0) -> tuple[JudgmentResponse, SpyProvider]:
    spy = SpyProvider(result)
    response = invoke_judgment(request, provider_factory=spy.factory, clock=_clock(now))
    return response, spy


def test_jc1_declared_choice_is_valid() -> None:
    response, spy = _invoke(_request(), _choice())
    assert response.choice == Choice("yes")
    assert response.error is None
    assert spy.calls == 1


def test_jc2_duplicate_choices_skip_provider() -> None:
    response, spy = _invoke(_request(allowed_choices=("yes", "yes")), _choice())
    assert response.error is JudgmentErrorCategory.INVALID_REQUEST
    assert spy.built == 0


def test_jc3_empty_identifier_is_invalid() -> None:
    response, spy = _invoke(_request(request_id=" "), _choice())
    assert response.error is JudgmentErrorCategory.INVALID_REQUEST
    assert spy.calls == 0


def test_jc4_latest_version_is_invalid() -> None:
    response, spy = _invoke(_request(model_version="model-latest"), _choice())
    assert response.error is JudgmentErrorCategory.INVALID_REQUEST
    other, other_spy = _invoke(_request(model_version="latest"), _choice())
    assert other.error is JudgmentErrorCategory.INVALID_REQUEST
    assert spy.built == 0
    assert other_spy.built == 0


def test_jc5_expired_deadline_skips_provider() -> None:
    response, spy = _invoke(_request(deadline_monotonic=50.0), _choice(), now=100.0)
    assert response.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert spy.calls == 0


def test_jc6_non_finite_deadline_is_invalid() -> None:
    response, spy = _invoke(_request(deadline_monotonic=math.nan), _choice())
    assert response.error is JudgmentErrorCategory.INVALID_REQUEST
    other, _other_spy = _invoke(_request(deadline_monotonic=math.inf), _choice())
    assert other.error is JudgmentErrorCategory.INVALID_REQUEST
    assert spy.built == 0


def test_jc7_secret_hosted_payload_is_denied() -> None:
    request = _request(
        data_class=DataClass.SECRET,
        network_boundary=NetworkBoundary.EXTERNAL,
        provider=EXTERNAL_PROVIDER,
        request_egress_authorized=True,
        hosted_boundary=True,
        payload={"token": "super-secret-token"},
    )
    response, spy = _invoke(request, _choice())
    assert response.error is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED
    assert spy.calls == 0


def test_jc8_private_client_hosted_is_denied() -> None:
    request = _request(
        data_class=DataClass.PRIVATE_CLIENT_DATA,
        network_boundary=NetworkBoundary.EXTERNAL,
        provider=EXTERNAL_PROVIDER,
        request_egress_authorized=True,
        hosted_boundary=True,
    )
    response, spy = _invoke(request, _choice())
    assert response.error is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED
    assert spy.calls == 0


def test_jc9_public_without_egress_is_denied() -> None:
    request = _request(
        data_class=DataClass.PUBLIC_NO_PII,
        network_boundary=NetworkBoundary.EXTERNAL,
        provider=EXTERNAL_PROVIDER,
        request_egress_authorized=False,
        hosted_boundary=True,
    )
    response, spy = _invoke(request, _choice())
    assert response.error is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED
    assert spy.calls == 0


def test_jc10_synthetic_hosted_may_call_provider() -> None:
    request = _request(
        data_class=DataClass.SYNTHETIC,
        network_boundary=NetworkBoundary.EXTERNAL,
        provider=EXTERNAL_PROVIDER,
        request_egress_authorized=True,
        hosted_boundary=True,
    )
    response, spy = _invoke(request, _choice(provider=EXTERNAL_PROVIDER))
    assert response.choice == Choice("yes")
    assert spy.calls == 1


def test_jc11_declared_choice_variant() -> None:
    response, _spy = _invoke(_request(), _choice("yes"))
    assert response.choice is not None
    assert response.noul is None
    assert response.error is None


def test_jc12_undeclared_choice_is_invalid_response() -> None:
    response, spy = _invoke(_request(), _choice("no"))
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert response.choice is None
    assert spy.calls == 1


def test_jc13_finite_score_inside_scale() -> None:
    scale = ScoreScale("fit", 0.0, 1.0)
    raw = _choice()
    raw = JudgmentResponse(
        provider=raw.provider,
        model=raw.model,
        model_version=raw.model_version,
        decision_pack_id=raw.decision_pack_id,
        decision_pack_version=raw.decision_pack_version,
        telemetry=raw.telemetry,
        choice=Choice("yes"),
        score=Score("fit", 0.5),
    )
    response, _spy = _invoke(_request(score_scale=scale), raw)
    assert response.score == Score("fit", 0.5)


def test_jc14_score_outside_scale() -> None:
    scale = ScoreScale("fit", 0.0, 1.0)
    raw = _choice()
    raw = JudgmentResponse(
        provider=raw.provider,
        model=raw.model,
        model_version=raw.model_version,
        decision_pack_id=raw.decision_pack_id,
        decision_pack_version=raw.decision_pack_version,
        telemetry=raw.telemetry,
        choice=Choice("yes"),
        score=Score("fit", 2.0),
    )
    response, _spy = _invoke(_request(score_scale=scale), raw)
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc15_nan_score_is_invalid() -> None:
    scale = ScoreScale("fit", 0.0, 1.0)
    raw = _scored(Score("fit", math.nan))
    response, _spy = _invoke(_request(score_scale=scale), raw)
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc16_infinite_score_is_invalid() -> None:
    scale = ScoreScale("fit", 0.0, 1.0)
    raw = _scored(Score("fit", math.inf))
    response, _spy = _invoke(_request(score_scale=scale), raw)
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc17_allowed_noul() -> None:
    raw = _bare(noul=Noul(NoulReason.NO_RELIABLE_JUDGMENT))
    response, _spy = _invoke(_request(noul_allowed=True), raw)
    assert response.noul == Noul(NoulReason.NO_RELIABLE_JUDGMENT)
    assert response.choice is None


def test_jc18_forbidden_noul() -> None:
    raw = _bare(noul=Noul(NoulReason.NO_RELIABLE_JUDGMENT))
    response, _spy = _invoke(_request(noul_allowed=False), raw)
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc19_noul_with_choice_is_invalid() -> None:
    raw = _bare(choice=Choice("yes"), noul=Noul(NoulReason.NO_RELIABLE_JUDGMENT))
    response, _spy = _invoke(_request(), raw)
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert response.noul is None
    assert response.choice is None


def test_jc20_both_variants_are_invalid() -> None:
    raw = _bare(choice=Choice("yes"), noul=Noul(NoulReason.NO_RELIABLE_JUDGMENT))
    response, _spy = _invoke(_request(), raw)
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc21_no_variant_is_invalid() -> None:
    response, _spy = _invoke(_request(), _bare())
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc22_provider_identity_mismatch() -> None:
    response, _spy = _invoke(_request(), _choice(provider="other-provider"))
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc23_model_version_mismatch() -> None:
    response, _spy = _invoke(_request(), _choice(model_version="9.9.9"))
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc24_decision_pack_version_mismatch() -> None:
    response, _spy = _invoke(_request(), _choice(decision_pack_version="99"))
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc25_typed_provider_error() -> None:
    raw = _bare(error=JudgmentErrorCategory.PROVIDER_UNAVAILABLE)
    response, _spy = _invoke(_request(), raw)
    assert response.error is JudgmentErrorCategory.PROVIDER_UNAVAILABLE
    assert response.choice is None


def test_jc26_unexpected_exception_is_internal() -> None:
    response, spy = _invoke(_request(), RuntimeError("payload secret leaked"))
    assert response.error is JudgmentErrorCategory.INTERNAL_ERROR
    assert "leaked" not in response_to_json(response)
    assert spy.calls == 1


def test_jc27_round_trip() -> None:
    request = _request(payload={"note": "synthetic"}, score_scale=ScoreScale("fit", 0.0, 1.0))
    restored = request_from_json(request_to_json(request))
    assert restored == request
    raw = _scored(Score("fit", 0.25))
    response, _spy = _invoke(request, raw)
    assert response_from_json(response_to_json(response)) == response


def test_jc28_telemetry_has_no_payload() -> None:
    request = _request(payload={"note": "synthetic-body"})
    response, _spy = _invoke(request, _choice())
    text = response_to_json(response)
    telemetry = text.split('"telemetry":', 1)[1]
    assert "synthetic-body" not in telemetry
    assert "payload" not in telemetry


def test_jc29_telemetry_has_no_secret() -> None:
    request = _request(payload={"token": "super-secret-token"})
    response, _spy = _invoke(request, _choice())
    telemetry = response_to_json(response).split('"telemetry":', 1)[1]
    assert "super-secret-token" not in telemetry


def test_jc30_privacy_before_provider_construction() -> None:
    request = _request(
        data_class=DataClass.SECRET,
        network_boundary=NetworkBoundary.EXTERNAL,
        provider=EXTERNAL_PROVIDER,
        request_egress_authorized=True,
        hosted_boundary=True,
    )
    response, spy = _invoke(request, _choice())
    assert response.error is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED
    assert spy.built == 0


def test_jc31_deadline_before_provider_invocation() -> None:
    response, spy = _invoke(_request(deadline_monotonic=1.0), _choice(), now=5.0)
    assert response.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert spy.built == 0
    assert spy.calls == 0


def test_jc32_invalid_response_hides_bad_choice() -> None:
    response, _spy = _invoke(_request(), _choice("not-declared"))
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert response.choice is None
    assert "not-declared" not in response_to_json(response)


def test_jc33_noul_is_not_approval() -> None:
    raw = _bare(noul=Noul(NoulReason.NO_RELIABLE_JUDGMENT))
    response, _spy = _invoke(_request(), raw)
    assert response.noul is not None
    assert not hasattr(response.noul, "choice")
    assert grants_authority(response) is False
    assert "automatic_approval" not in response_to_json(response)


def test_jc34_choice_does_not_grant_completion() -> None:
    response, _spy = _invoke(_request(), _choice())
    assert response.choice == Choice("yes")
    assert grants_authority(response) is False
    assert "completion_authority" not in response_to_json(response)


def _bare(**variants: object) -> JudgmentResponse:
    return JudgmentResponse(
        provider=LOCAL_PROVIDER,
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


def test_retry_count_stays_zero() -> None:
    response, _spy = _invoke(_request(), _choice())
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
        response, _spy = _invoke(_request(), sample)
        assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
        assert response.choice is None
        assert response.noul is None


def test_r2_late_choice_is_deadline_exhausted() -> None:
    class Clock:
        def __init__(self) -> None:
            self.reads = 0

        def __call__(self) -> float:
            self.reads += 1
            # Старт, срок до фабрики и срок после фабрики остаются внутри.
            if self.reads <= 3:
                return 10.0
            return 500.0

    late = SpyProvider(_choice())
    response = invoke_judgment(
        _request(deadline_monotonic=100.0),
        provider_factory=late.factory,
        clock=Clock(),
    )
    assert response.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert response.choice is None
    assert "yes" not in response_to_json(response)


def test_r2_on_time_choice_stays_valid() -> None:
    response, _spy = _invoke(_request(deadline_monotonic=200.0), _choice(), now=100.0)
    assert response.choice == Choice("yes")
    assert response.error is None


def test_r3_selector_pins_are_invalid() -> None:
    for pin in ("*", "jev-*", ">=1", "^1.2", "~1.2", "1.x", "latest"):
        response, spy = _invoke(_request(model_version=pin), _choice())
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST
        assert spy.built == 0


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
    answer = json.loads(response_to_json(_invoke(_request(), _choice())[0]))
    answer["choice"] = 1
    with pytest.raises(ValueError):
        response_from_json(json.dumps(answer))


def test_b1_noul_reason_is_bounded() -> None:
    valid, _spy = _invoke(_request(), _bare(noul=Noul(NoulReason.INSUFFICIENT_EVIDENCE)))
    assert valid.noul == Noul(NoulReason.INSUFFICIENT_EVIDENCE)
    restored = response_from_json(response_to_json(valid))
    assert restored.noul == valid.noul
    leaked, _other = _invoke(_request(), _bare(noul=Noul("super-secret-token sentence")))  # type: ignore[arg-type]
    assert leaked.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert "super-secret-token" not in response_to_json(leaked)
    document = json.loads(response_to_json(valid))
    document["noul"] = "the model cannot decide"
    with pytest.raises(ValueError):
        response_from_json(json.dumps(document))


def test_b2_response_json_invariants() -> None:
    valid, _spy = _invoke(_request(), _choice())
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
        response, spy = _invoke(_request(allowed_choices=choices), _choice())  # type: ignore[arg-type]
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST
        assert spy.built == 0
    ok, spy = _invoke(_request(allowed_choices=("yes",)), _choice())
    assert ok.choice == Choice("yes")
    assert spy.calls == 1


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
        response, spy = _invoke(_request(model_version=pin), _choice(model_version=pin))
        assert response.error is None, pin
        assert spy.calls == 1
    rejected = (
        "*",
        "jev-*",
        "latest",
        "model-latest",
        ">=1",
        ">1",
        "<=2",
        "<2",
        "^1.2",
        "~1.2",
        "1.x",
        "1.*",
        "1 || 2",
        "1 - 2",
        "1 && 2",
        "1 | 2",
        "1 & 2",
        "1 + 2",
        "1 / 2",
        "1\\2",
        "1,2",
        "1 2",
        "(1)",
        "[1]",
        "{1}",
        " leading-space",
        "trailing-space ",
    )
    for pin in rejected:
        response, spy = _invoke(_request(model_version=pin), _choice())
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST, pin
        assert spy.built == 0


def test_c1_external_boundary_does_not_trust_hosted_flag() -> None:
    def run(data_class: DataClass, boundary: NetworkBoundary, egress: bool, hosted: bool):
        provider = EXTERNAL_PROVIDER if boundary is NetworkBoundary.EXTERNAL else LOCAL_PROVIDER
        fixture = SpyProvider(_choice(provider=provider))
        response = invoke_judgment(
            _request(
                data_class=data_class,
                network_boundary=boundary,
                request_egress_authorized=egress,
                hosted_boundary=hosted,
                outbound_form=OutboundForm.RAW,
                provider=provider,
            ),
            provider_factory=fixture.factory,
            clock=_clock(10.0),
        )
        return response, fixture

    allowed, called = run(DataClass.SYNTHETIC, NetworkBoundary.EXTERNAL, True, True)
    assert allowed.choice == Choice("yes")
    assert called.calls == 1
    public, public_calls = run(DataClass.PUBLIC_NO_PII, NetworkBoundary.EXTERNAL, True, True)
    assert public.choice == Choice("yes")
    assert public_calls.calls == 1
    for data_class in (DataClass.PUBLIC_POSSIBLE_PII, DataClass.PRIVATE_CLIENT_DATA, DataClass.SECRET):
        denied, fixture = run(data_class, NetworkBoundary.EXTERNAL, True, True)
        assert denied.error is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED
        assert fixture.calls == 0
    disguised, fixture = run(DataClass.PRIVATE_CLIENT_DATA, NetworkBoundary.EXTERNAL, True, False)
    assert disguised.error is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED
    assert fixture.calls == 0
    no_egress, fixture = run(DataClass.SYNTHETIC, NetworkBoundary.EXTERNAL, False, True)
    assert no_egress.error is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED
    assert fixture.calls == 0
    contradiction, fixture = run(DataClass.SYNTHETIC, NetworkBoundary.LOCAL_SAME_HOST, False, True)
    assert contradiction.error is JudgmentErrorCategory.INVALID_REQUEST
    assert fixture.calls == 0


def test_c2_deadline_covers_validation() -> None:
    class SequenceClock:
        def __init__(self, values: list[float]) -> None:
            self.values = list(values)

        def __call__(self) -> float:
            return self.values.pop(0)

    late_validation = invoke_judgment(
        _request(deadline_monotonic=1.0),
        provider_factory=SpyProvider(_choice()).factory,
        clock=SequenceClock([0.0, 0.0, 0.4, 0.9, 1.1]),
    )
    assert late_validation.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert late_validation.choice is None
    late_provider = invoke_judgment(
        _request(deadline_monotonic=1.0),
        provider_factory=SpyProvider(_choice()).factory,
        clock=SequenceClock([0.0, 0.0, 0.4, 1.2, 1.3]),
    )
    assert late_provider.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert "yes" not in response_to_json(late_provider)
    on_time = invoke_judgment(
        _request(deadline_monotonic=5.0),
        provider_factory=SpyProvider(_choice()).factory,
        clock=SequenceClock([0.0, 0.0, 0.1, 0.2, 0.4]),
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
        fixture = SpyProvider(_choice())
        response = invoke_judgment(_request(**overrides), provider_factory=fixture.factory, clock=_clock(1.0))  # type: ignore[arg-type]
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST
        assert fixture.calls == 0
        assert response.provider == "unvalidated"
        rendered = response_to_json(response)
        assert "None" not in rendered
        assert "{}" not in rendered


def test_c4_telemetry_outcome_is_closed() -> None:
    choice, _spy = _invoke(_request(), _choice())
    noul, _other = _invoke(_request(), _bare(noul=Noul(NoulReason.NO_RELIABLE_JUDGMENT)))
    failure, _third = _invoke(_request(), _bare(error=JudgmentErrorCategory.PROVIDER_UNAVAILABLE))
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
    """UNKNOWN не даёт права ни одному классу. hosted_boundary=false это не меняет."""
    for data_class in DataClass:
        for hosted in (False, True):
            fixture = SpyProvider(_choice())
            response = invoke_judgment(
                _request(
                    data_class=data_class,
                    network_boundary=NetworkBoundary.UNKNOWN_BOUNDARY,
                    request_egress_authorized=True,
                    hosted_boundary=hosted,
                ),
                provider_factory=fixture.factory,
                clock=_clock(1.0),
            )
            assert response.error in {
                JudgmentErrorCategory.PRIVACY_EGRESS_DENIED,
                JudgmentErrorCategory.INVALID_REQUEST,
            }
            assert fixture.built == 0
            assert fixture.calls == 0


def test_d1_privacy_matrix_uses_real_enums() -> None:
    external_denied = {DataClass.PUBLIC_POSSIBLE_PII, DataClass.PRIVATE_CLIENT_DATA, DataClass.SECRET}
    hosted_ok = {DataClass.SYNTHETIC, DataClass.PUBLIC_NO_PII}
    aligned = {
        NetworkBoundary.LOCAL_SAME_HOST: LOCAL_PROVIDER,
        NetworkBoundary.INTERNAL_TRUSTED: INTERNAL_PROVIDER,
        NetworkBoundary.EXTERNAL: EXTERNAL_PROVIDER,
        NetworkBoundary.UNKNOWN_BOUNDARY: LOCAL_PROVIDER,
    }
    for boundary in NetworkBoundary:
        for data_class in DataClass:
            for egress in (False, True):
                for hosted in (False, True):
                    provider = aligned[boundary]
                    fixture = SpyProvider(_choice(provider=provider))
                    response = invoke_judgment(
                        _request(
                            data_class=data_class,
                            network_boundary=boundary,
                            request_egress_authorized=egress,
                            hosted_boundary=hosted,
                            provider=provider,
                        ),
                        provider_factory=fixture.factory,
                        clock=_clock(1.0),
                    )
                    contradictory = hosted is True and boundary is not NetworkBoundary.EXTERNAL
                    denied = (
                        contradictory
                        or boundary is NetworkBoundary.UNKNOWN_BOUNDARY
                        or data_class is DataClass.SECRET
                        or (boundary is NetworkBoundary.EXTERNAL and (egress is False or data_class in external_denied))
                    )
                    if denied:
                        assert fixture.built == 0
                        assert fixture.calls == 0
                    else:
                        assert response.choice == Choice("yes")
                        assert fixture.calls == 1


def test_d2_factory_expiry_skips_judge() -> None:
    class Clock:
        def __init__(self) -> None:
            self.after_factory = False

        def __call__(self) -> float:
            return 1.1 if self.after_factory else 0.2

    clock = Clock()
    fixture = SpyProvider(_choice())

    def factory():
        clock.after_factory = True
        return fixture.factory()

    response = invoke_judgment(_request(deadline_monotonic=1.0), provider_factory=factory, clock=clock)
    assert response.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert fixture.built == 1
    assert fixture.calls == 0


def test_d3_huge_deadline_is_invalid_request() -> None:
    for value in (10**400, -(10**400), float("nan"), float("inf"), float("-inf"), True, "1"):
        fixture = SpyProvider(_choice())
        response = invoke_judgment(
            _request(deadline_monotonic=value),  # type: ignore[arg-type]
            provider_factory=fixture.factory,
            clock=_clock(1.0),
        )
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST
        assert fixture.built == 0
    huge_scale = invoke_judgment(
        _request(score_scale=ScoreScale("fit", 0.0, 10**400)),  # type: ignore[arg-type]
        provider_factory=SpyProvider(_choice()).factory,
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
        response, _spy = _invoke(_request(score_scale=scale), raw)
        assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


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
        fixture = SpyProvider(_choice())
        response = invoke_judgment(_request(), provider_factory=fixture.factory, clock=clock)
        assert response.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
        assert response.choice is None
        assert fixture.built == 0
        assert fixture.calls == 0
    zero = invoke_judgment(
        _request(deadline_monotonic=1.0),
        provider_factory=SpyProvider(_choice()).factory,
        clock=lambda: 0.0,
    )
    assert zero.choice == Choice("yes")


def test_f1_trusted_provider_boundary_is_authoritative() -> None:
    mismatch = SpyProvider(_choice())
    response = invoke_judgment(
        _request(
            provider=EXTERNAL_PROVIDER,
            network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
            data_class=DataClass.PRIVATE_CLIENT_DATA,
            request_egress_authorized=False,
        ),
        provider_factory=mismatch.factory,
        clock=_clock(1.0),
    )
    assert response.error is JudgmentErrorCategory.INVALID_REQUEST
    assert mismatch.built == 0
    assert mismatch.calls == 0
    private = SpyProvider(_choice(provider=EXTERNAL_PROVIDER))
    denied = invoke_judgment(
        _request(
            provider=EXTERNAL_PROVIDER,
            network_boundary=NetworkBoundary.EXTERNAL,
            data_class=DataClass.PRIVATE_CLIENT_DATA,
            request_egress_authorized=True,
            hosted_boundary=True,
        ),
        provider_factory=private.factory,
        clock=_clock(1.0),
    )
    assert denied.error is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED
    assert private.built == 0
    assert private.calls == 0
    allowed = SpyProvider(_choice(provider=EXTERNAL_PROVIDER))
    opened = invoke_judgment(
        _request(
            provider=EXTERNAL_PROVIDER,
            network_boundary=NetworkBoundary.EXTERNAL,
            data_class=DataClass.SYNTHETIC,
            request_egress_authorized=True,
            hosted_boundary=True,
        ),
        provider_factory=allowed.factory,
        clock=_clock(1.0),
    )
    assert opened.choice == Choice("yes")
    assert allowed.calls == 1
    local_as_external = SpyProvider(_choice())
    crossed = invoke_judgment(
        _request(provider=LOCAL_PROVIDER, network_boundary=NetworkBoundary.EXTERNAL, hosted_boundary=True),
        provider_factory=local_as_external.factory,
        clock=_clock(1.0),
    )
    assert crossed.error is JudgmentErrorCategory.INVALID_REQUEST
    assert local_as_external.built == 0
    consistent = invoke_judgment(
        _request(provider=LOCAL_PROVIDER, network_boundary=NetworkBoundary.LOCAL_SAME_HOST),
        provider_factory=SpyProvider(_choice()).factory,
        clock=_clock(1.0),
    )
    assert consistent.choice == Choice("yes")
    unknown = SpyProvider(_choice())
    missing = invoke_judgment(
        _request(provider="not-a-governed-provider"),
        provider_factory=unknown.factory,
        clock=_clock(1.0),
    )
    assert missing.error is JudgmentErrorCategory.INVALID_REQUEST
    assert unknown.built == 0
    assert unknown.calls == 0


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

    ok, spy = _invoke(_request(), _choice())
    assert ok.choice == Choice("yes")
    assert spy.calls == 1
    for overrides in (
        {"decision_pack_version": "999"},
        {"decision_pack_id": "other-pack"},
        {"decision_pack_id": "pack-typo"},
    ):
        fixture = SpyProvider(_choice())
        response = invoke_judgment(
            _request(**overrides),
            provider_factory=fixture.factory,
            clock=_clock(1.0),
            decision_pack_known=known,
        )
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST
        assert fixture.built == 0
        assert fixture.calls == 0
    broken = SpyProvider(_choice())

    def explode(pack_id: str, version: str) -> bool:
        raise RuntimeError("resolver down")

    failed = invoke_judgment(
        _request(),
        provider_factory=broken.factory,
        clock=_clock(1.0),
        decision_pack_known=explode,
    )
    assert failed.error is JudgmentErrorCategory.INVALID_REQUEST
    assert broken.built == 0
    closed = SpyProvider(_choice())
    absent = invoke_judgment(
        _request(),
        provider_factory=closed.factory,
        clock=_clock(1.0),
        decision_pack_known=None,
    )
    assert absent.error is JudgmentErrorCategory.INVALID_REQUEST
    assert closed.built == 0


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
        response, spy = _invoke(_request(), raw)
        assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
        assert spy.calls == 1
        with pytest.raises(ValueError):
            response_to_json(raw)
    for field in fields:
        raw = _choice()
        telemetry = JudgmentTelemetry(
            JudgmentOutcome.CHOICE,
            None,
            0,
            0,
            raw.provider,
            raw.model,
            raw.model_version,
            raw.decision_pack_id,
            raw.decision_pack_version,
        )
        object.__setattr__(telemetry, field, Hostile())
        hostile = JudgmentResponse(
            provider=raw.provider,
            model=raw.model,
            model_version=raw.model_version,
            decision_pack_id=raw.decision_pack_id,
            decision_pack_version=raw.decision_pack_version,
            telemetry=telemetry,
            choice=Choice("yes"),
        )
        response, _spy = _invoke(_request(), hostile)
        assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
        with pytest.raises(ValueError):
            response_to_json(hostile)


def test_g1_factory_starts_only_after_privacy() -> None:
    order: list[str] = []

    class Tracking:
        def __init__(self) -> None:
            order.append("construct")

        def judge(self, request: JudgmentRequest) -> JudgmentResponse:
            order.append("judge")
            return _choice(provider=EXTERNAL_PROVIDER)

    def factory() -> Tracking:
        return Tracking()

    denied = invoke_judgment(
        _request(
            provider=EXTERNAL_PROVIDER,
            network_boundary=NetworkBoundary.EXTERNAL,
            data_class=DataClass.SECRET,
            request_egress_authorized=True,
            hosted_boundary=True,
        ),
        provider_factory=factory,
        clock=_clock(1.0),
    )
    assert denied.error is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED
    assert order == []
    allowed = invoke_judgment(
        _request(
            provider=EXTERNAL_PROVIDER,
            network_boundary=NetworkBoundary.EXTERNAL,
            data_class=DataClass.SYNTHETIC,
            request_egress_authorized=True,
            hosted_boundary=True,
        ),
        provider_factory=factory,
        clock=_clock(1.0),
    )
    assert allowed.choice == Choice("yes")
    assert order == ["construct", "judge"]


def test_g2_clock_callback_exceptions_fail_closed() -> None:
    for kind in (RuntimeError, OSError):
        fixture = SpyProvider(_choice())

        def clock() -> float:
            raise kind("clock")

        response = invoke_judgment(_request(), provider_factory=fixture.factory, clock=clock)
        assert response.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
        assert fixture.built == 0
        assert fixture.calls == 0
