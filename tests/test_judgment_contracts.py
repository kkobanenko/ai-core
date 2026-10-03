"""Канонический пакетный контракт J1. Noul здесь не нейтральный термин."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from ai_core.capabilities import ProviderCapability
from ai_core.judgment_contracts import (
    BinaryAnswer,
    BinaryQuestion,
    ChoiceAnswer,
    ChoiceQuestion,
    JudgmentErrorCategory,
    JudgmentOutcome,
    JudgmentRequest,
    JudgmentResponse,
    ScoreAnswer,
    ScoreQuestion,
    _DISTRIBUTION_SUM_TOLERANCE,
    _MAX_QUESTIONS,
    grants_authority,
    invoke_judgment as _invoke_judgment,
    request_from_json,
    request_to_json,
    response_from_json,
    response_to_json,
)
from ai_core.judgment_mock import MOCK_PROVIDER_ID, MockBehavior, MockVariant
from ai_core.privacy import DataClass, OutboundForm
from ai_core.provider_catalog import NetworkBoundary


def _known_pack(pack_id: str, version: str) -> bool:
    return pack_id == "pack-1" and version == "1"


def invoke_judgment(request, **kwargs):
    kwargs.setdefault("decision_pack_known", _known_pack)
    return _invoke_judgment(request, **kwargs)


def _clock(now: float):
    def read() -> float:
        return now

    return read


def _questions(**extra: object) -> tuple:
    base = (("same", BinaryQuestion("same entity")),)
    if not extra:
        return base
    return extra["questions"]  # type: ignore[return-value]


def _request(**overrides: object) -> JudgmentRequest:
    values: dict = {
        "request_id": "req-1",
        "decision_pack_id": "pack-1",
        "decision_pack_version": "1",
        "questions": (("same", BinaryQuestion("same entity")),),
        "data_class": DataClass.SYNTHETIC,
        "outbound_form": OutboundForm.RAW,
        "network_boundary": NetworkBoundary.LOCAL_SAME_HOST,
        "request_egress_authorized": False,
        "hosted_boundary": False,
        "deadline_monotonic": 200.0,
        "provider": MOCK_PROVIDER_ID,
        "model": "fixture-model",
        "model_version": "1",
        "payload": {"note": "synthetic"},
    }
    values.update(overrides)
    return JudgmentRequest(**values)


def _binary_answer(probability: float = 1.0) -> tuple:
    return (("same", BinaryAnswer(probability)),)


def test_binary_probability_bounds() -> None:
    for value in (0.0, 1.0, 0.25):
        behavior = MockBehavior(binary_probability=value)
        response = invoke_judgment(_request(), mock_behavior=behavior, clock=_clock(1.0))
        assert response.error is None
        assert response.answers == _binary_answer(value)
    for value in (float("nan"), float("inf"), -0.1, 1.1, True, "bad"):
        behavior = MockBehavior(binary_probability=value)  # type: ignore[arg-type]
        response = invoke_judgment(_request(), mock_behavior=behavior, clock=_clock(1.0))
        assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
        assert response.answers is None


def test_choice_distribution_rules() -> None:
    question = ChoiceQuestion(("no", "yes"))
    request = _request(questions=(("label", question),))
    valid = invoke_judgment(request, clock=_clock(1.0))
    assert valid.error is None
    answer = valid.answers[0][1]
    assert isinstance(answer, ChoiceAnswer)
    assert answer.selected_choice == "no"
    assert abs(sum(item[1] for item in answer.probabilities) - 1.0) <= _DISTRIBUTION_SUM_TOLERANCE

    def run(answer_obj: ChoiceAnswer) -> JudgmentErrorCategory | None:
        raw = JudgmentResponse(
            provider=request.provider,
            model=request.model,
            model_version=request.model_version,
            decision_pack_id=request.decision_pack_id,
            decision_pack_version=request.decision_pack_version,
            telemetry=valid.telemetry,
            answers=(("label", answer_obj),),
        )
        from ai_core.judgment_contracts import validate_response_for_request

        return validate_response_for_request(raw, request)

    good = (("no", 0.25), ("yes", 0.75))
    assert run(ChoiceAnswer("yes", 0.75, good)) is None
    assert run(ChoiceAnswer("maybe", 0.5, good)) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert run(ChoiceAnswer("yes", 0.75, (("no", 1.0),))) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert run(ChoiceAnswer("yes", 0.75, (("no", 0.2), ("yes", 0.2), ("extra", 0.6)))) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert run(ChoiceAnswer("yes", 0.5, (("no", -0.1), ("yes", 1.1)))) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert run(ChoiceAnswer("yes", 0.5, (("no", 2.0), ("yes", -1.0)))) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert run(ChoiceAnswer("yes", 0.5, (("no", float("nan")), ("yes", 1.0)))) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    low = (("no", 0.1), ("yes", 0.1))
    high = (("no", 0.9), ("yes", 0.9))
    assert run(ChoiceAnswer("yes", 0.5, low)) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert run(ChoiceAnswer("yes", 0.5, high)) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert run(ChoiceAnswer("yes", -0.1, good)) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert run(ChoiceAnswer("yes", 1.1, good)) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_score_scale_and_distribution() -> None:
    question = ScoreQuestion(("high", "low"), 0.0, 1.0)
    request = _request(questions=(("fit", question),))
    valid = invoke_judgment(request, clock=_clock(1.0))
    assert valid.error is None
    answer = valid.answers[0][1]
    assert isinstance(answer, ScoreAnswer)
    assert answer.expected_score == 0.0

    def run(answer_obj: ScoreAnswer):
        raw = JudgmentResponse(
            provider=request.provider,
            model=request.model,
            model_version=request.model_version,
            decision_pack_id=request.decision_pack_id,
            decision_pack_version=request.decision_pack_version,
            telemetry=valid.telemetry,
            answers=(("fit", answer_obj),),
        )
        from ai_core.judgment_contracts import validate_response_for_request

        return validate_response_for_request(raw, request)

    probs = (("high", 0.4), ("low", 0.6))
    assert run(ScoreAnswer(0.5, 0.6, probs)) is None
    assert run(ScoreAnswer(-0.1, 0.6, probs)) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert run(ScoreAnswer(float("inf"), 0.6, probs)) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert run(ScoreAnswer(0.5, 0.6, (("high", 1.0),))) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert run(ScoreAnswer(0.5, 0.6, (("high", 0.2), ("low", 0.2)))) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert run(ScoreAnswer(0.5, 1.2, probs)) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_batch_answer_set() -> None:
    questions = (
        ("fit", ScoreQuestion(("high", "low"), 0.0, 1.0)),
        ("label", ChoiceQuestion(("no", "yes"))),
        ("same", BinaryQuestion("same entity", "duplicate", "distinct")),
    )
    response = invoke_judgment(_request(questions=questions), clock=_clock(1.0))
    assert response.error is None
    assert response.answers is not None
    assert tuple(name for name, _answer in response.answers) == tuple(name for name, _question in questions)
    assert isinstance(response.answers[0][1], ScoreAnswer)
    assert isinstance(response.answers[1][1], ChoiceAnswer)
    assert isinstance(response.answers[2][1], BinaryAnswer)
    one = invoke_judgment(_request(), clock=_clock(1.0))
    assert one.answers is not None and len(one.answers) == 1


def test_batch_rejects_missing_extra_and_wrong_variant() -> None:
    request = _request(questions=(("label", ChoiceQuestion(("no", "yes"))), ("same", BinaryQuestion("same entity"))))
    ok = invoke_judgment(request, clock=_clock(1.0))

    def check(answers):
        raw = JudgmentResponse(
            provider=request.provider,
            model=request.model,
            model_version=request.model_version,
            decision_pack_id=request.decision_pack_id,
            decision_pack_version=request.decision_pack_version,
            telemetry=ok.telemetry,
            answers=answers,
        )
        from ai_core.judgment_contracts import validate_response_for_request

        return validate_response_for_request(raw, request)

    only_one = (ok.answers[0],)
    assert check(only_one) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    extra = ok.answers + (("other", BinaryAnswer(1.0)),)
    assert check(extra) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    swapped = (
        ("label", BinaryAnswer(1.0)),
        ("same", ChoiceAnswer("yes", 1.0, (("yes", 1.0),))),
    )
    assert check(swapped) is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE


def test_question_names_are_bounded() -> None:
    duplicate = invoke_judgment(
        _request(questions=(("same", BinaryQuestion("a")), ("same", BinaryQuestion("b")))),
        clock=_clock(1.0),
    )
    assert duplicate.error is JudgmentErrorCategory.INVALID_REQUEST
    empty = invoke_judgment(_request(questions=(("", BinaryQuestion("a")),)), clock=_clock(1.0))
    assert empty.error is JudgmentErrorCategory.INVALID_REQUEST
    too_many = tuple((f"q{index}", BinaryQuestion("a")) for index in range(_MAX_QUESTIONS + 1))
    overflow = invoke_judgment(_request(questions=too_many), clock=_clock(1.0))
    assert overflow.error is JudgmentErrorCategory.INVALID_REQUEST


def test_execution_failure_hides_answers() -> None:
    behavior = MockBehavior(variant=MockVariant.ERROR, error_category=JudgmentErrorCategory.PROVIDER_UNAVAILABLE)
    response = invoke_judgment(_request(), mock_behavior=behavior, clock=_clock(1.0))
    assert response.error is JudgmentErrorCategory.PROVIDER_UNAVAILABLE
    assert response.answers is None
    assert response.telemetry.outcome is JudgmentOutcome.ERROR
    rendered = response_to_json(response)
    assert "same entity" not in rendered
    assert "probability_true" not in rendered


def test_real_provider_and_caller_code_cannot_execute() -> None:
    for provider in ("mistral_external", "gpu_ollama", "ollama_cloud", "vm100_local_ollama"):
        response = invoke_judgment(_request(provider=provider), clock=_clock(1.0))
        assert response.error is JudgmentErrorCategory.INVALID_REQUEST
        assert response.answers is None
    assert not hasattr(ProviderCapability, "JUDGMENT")


def test_privacy_and_unknown_pack_and_deadline_skip_mock() -> None:
    secret = invoke_judgment(_request(data_class=DataClass.SECRET), clock=_clock(1.0))
    assert secret.error is JudgmentErrorCategory.PRIVACY_EGRESS_DENIED
    assert secret.answers is None
    unknown = invoke_judgment(_request(), decision_pack_known=lambda pack_id, version: False, clock=_clock(1.0))
    assert unknown.error is JudgmentErrorCategory.INVALID_REQUEST
    late = invoke_judgment(_request(deadline_monotonic=1.0), clock=_clock(5.0))
    assert late.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert late.answers is None


def test_backward_clock_and_invalid_clock() -> None:
    class Sequence:
        def __init__(self, values: list[float]) -> None:
            self.values = list(values)
            self.last = values[-1]

        def __call__(self) -> float:
            if self.values:
                self.last = self.values.pop(0)
            return self.last

    back = invoke_judgment(_request(deadline_monotonic=150.0), clock=Sequence([100.0, 90.0]))
    assert back.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert back.answers is None
    stepped = invoke_judgment(_request(deadline_monotonic=150.0), clock=Sequence([100.0, 101.0, 99.0]))
    assert stepped.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    same = invoke_judgment(_request(deadline_monotonic=150.0), clock=Sequence([100.0, 100.0, 100.0]))
    assert same.answers is not None
    bad = invoke_judgment(_request(), clock=lambda: float("nan"))
    assert bad.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert bad.telemetry.latency_ms == 0


def test_invalid_answer_does_not_grant_authority() -> None:
    behavior = MockBehavior(variant=MockVariant.INVALID_RESPONSE)
    response = invoke_judgment(_request(), mock_behavior=behavior, clock=_clock(1.0))
    assert response.error is JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    assert response.answers is None
    success = invoke_judgment(_request(), clock=_clock(1.0))
    assert grants_authority(success) is False
    rendered = response_to_json(success)
    assert "payload" not in rendered.split('"telemetry":', 1)[1]
    assert "same entity" not in rendered.split('"telemetry":', 1)[1]


def test_json_round_trip_rejects_nan_and_legacy_noul() -> None:
    request = _request(questions=(("same", BinaryQuestion("same entity", "duplicate", None)),))
    assert request_from_json(request_to_json(request)) == request
    response = invoke_judgment(request, clock=_clock(1.0))
    assert response_from_json(response_to_json(response)) == response
    with pytest.raises(ValueError):
        request_to_json(_request(payload={"value": float("nan")}))
    legacy = json.loads(request_to_json(request))
    legacy["noul_allowed"] = True
    with pytest.raises(ValueError):
        request_from_json(json.dumps(legacy))


def test_resolver_timeout_is_not_deadline_while_budget_remains() -> None:
    def explode(pack_id: str, version: str) -> bool:
        raise TimeoutError("resolver")

    response = invoke_judgment(_request(deadline_monotonic=100.0), decision_pack_known=explode, clock=_clock(1.0))
    assert response.error is JudgmentErrorCategory.INVALID_REQUEST
    assert response.answers is None


def test_blocking_mock_hits_deadline() -> None:
    started = time.monotonic()
    response = invoke_judgment(
        _request(deadline_monotonic=started + 0.1),
        mock_behavior=MockBehavior(variant=MockVariant.TIMEOUT, timeout_seconds=2.0),
    )
    assert response.error is JudgmentErrorCategory.DEADLINE_EXHAUSTED
    assert response.answers is None
    assert time.monotonic() - started < 1.5


def test_correction_is_documented_without_provider_neutral_noul() -> None:
    root = Path(__file__).resolve().parents[1]
    spec = (root / "specs/003-judgment-provider/spec.md").read_text(encoding="utf-8")
    assert "717cace0d109105c406723de30cd72e4e3ed7dd4" in spec
    assert "operator-decision-j1-contract-semantics-correction.yaml" in spec
    assert "BinaryQuestion" in spec
    source = (root / "src/ai_core/judgment_contracts.py").read_text(encoding="utf-8")
    assert "class Noul" not in source
    assert "class NoulReason" not in source
    assert "noul_allowed" not in source
    assert "NOUL" not in source
