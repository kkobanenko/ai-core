"""Контракт J1. Фикстура не является провайдером каталога."""

from __future__ import annotations

import math

from ai_core.judgment_contracts import (
    Choice,
    JudgmentErrorCategory,
    JudgmentRequest,
    JudgmentResponse,
    JudgmentTelemetry,
    Noul,
    Score,
    ScoreScale,
    grants_authority,
    invoke_judgment,
    request_from_json,
    request_to_json,
    response_from_json,
    response_to_json,
)
from ai_core.privacy import DataClass, OutboundForm
from ai_core.provider_catalog import NetworkBoundary


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
        "provider": "fixture-provider",
        "model": "fixture-model",
        "model_version": "1.0.0",
        "payload": {"note": "synthetic"},
        "score_scale": None,
    }
    values.update(overrides)
    return JudgmentRequest(**values)


def _telemetry() -> JudgmentTelemetry:
    return JudgmentTelemetry("choice", "", 0, 0, "fixture-provider", "fixture-model", "1.0.0", "pack-1", "1")


def _choice(value: str = "yes", **identity: str) -> JudgmentResponse:
    base = {
        "provider": "fixture-provider",
        "model": "fixture-model",
        "model_version": "1.0.0",
        "decision_pack_id": "pack-1",
        "decision_pack_version": "1",
    }
    base.update(identity)
    return JudgmentResponse(telemetry=_telemetry(), choice=Choice(value), **base)


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
        request_egress_authorized=True,
        hosted_boundary=True,
    )
    response, spy = _invoke(request, _choice())
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
    raw = _bare(noul=Noul("unknown"))
    response, _spy = _invoke(_request(noul_allowed=True), raw)
    assert response.noul == Noul("unknown")
    assert response.choice is None


def test_jc18_forbidden_noul() -> None:
    raw = _bare(noul=Noul("unknown"))
    response, _spy = _invoke(_request(noul_allowed=False), raw)
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_jc19_noul_with_choice_is_invalid() -> None:
    raw = _bare(choice=Choice("yes"), noul=Noul("unknown"))
    response, _spy = _invoke(_request(), raw)
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert response.noul is None
    assert response.choice is None


def test_jc20_both_variants_are_invalid() -> None:
    raw = _bare(choice=Choice("yes"), noul=Noul("unknown"))
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
    raw = _bare(noul=Noul("unknown"))
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
        provider="fixture-provider",
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
