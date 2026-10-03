"""Мок J1 отвечает на пакет вопросов и не ходит в сеть."""

from ai_core.judgment_contracts import BinaryAnswer, BinaryQuestion, ChoiceAnswer, ChoiceQuestion, JudgmentErrorCategory, JudgmentRequest
from ai_core.judgment_mock import MOCK_PROVIDER_ID, DeterministicMockJudgmentProvider, MockBehavior, MockVariant
from ai_core.privacy import DataClass, OutboundForm
from ai_core.provider_catalog import NetworkBoundary


def _request() -> JudgmentRequest:
    return JudgmentRequest(
        request_id="req-1",
        decision_pack_id="pack-1",
        decision_pack_version="1",
        questions=(
            ("same", BinaryQuestion("same entity")),
            ("label", ChoiceQuestion(("no", "yes"))),
        ),
        data_class=DataClass.SYNTHETIC,
        outbound_form=OutboundForm.RAW,
        network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
        request_egress_authorized=False,
        hosted_boundary=False,
        deadline_monotonic=10.0,
        provider=MOCK_PROVIDER_ID,
        model="fixture-model",
        model_version="1",
        payload=None,
    )


def test_mock_answers_each_question() -> None:
    response = DeterministicMockJudgmentProvider().judge(_request())
    assert response.error is None
    assert response.answers is not None
    assert response.answers[0][1] == BinaryAnswer(1.0)
    assert isinstance(response.answers[1][1], ChoiceAnswer)


def test_mock_error_has_no_answers() -> None:
    behavior = MockBehavior(variant=MockVariant.ERROR, error_category=JudgmentErrorCategory.PROVIDER_UNAVAILABLE)
    response = DeterministicMockJudgmentProvider(behavior).judge(_request())
    assert response.answers is None
    assert response.error is JudgmentErrorCategory.PROVIDER_UNAVAILABLE


def test_mock_invalid_fixture_is_not_a_secret_channel() -> None:
    response = DeterministicMockJudgmentProvider(MockBehavior(variant=MockVariant.INVALID_RESPONSE)).judge(_request())
    assert response.answers is not None
    assert isinstance(response.answers[0][1], BinaryAnswer)
