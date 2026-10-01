"""Контрактные типы judgment J1."""

import pytest

from ai_core.judgment_contracts import (
    BinaryAnswer,
    BinaryQuestion,
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionPackRef,
    JudgmentProviderPin,
    ScoreAnswer,
    ScoreQuestion,
)


def test_binary_answer_accepts_unit_interval_probability() -> None:
    answer = BinaryAnswer(probability_true=0.42)
    assert answer.probability_true == 0.42


def test_choice_question_rejects_duplicate_choices() -> None:
    with pytest.raises(ValueError):
        ChoiceQuestion(choices=("a", "a"))


def test_score_question_requires_finite_bounds() -> None:
    question = ScoreQuestion(levels=("low", "high"), min_score=0.0, max_score=1.0)
    assert question.levels == ("low", "high")


def test_provider_pin_is_exact_strings() -> None:
    pin = JudgmentProviderPin(
        provider_id="mock_judgment",
        model="jev-1.13.0",
        model_version="0.7.1",
    )
    assert pin.model == "jev-1.13.0"


def test_choice_answer_structure() -> None:
    answer = ChoiceAnswer(
        selected="yes",
        confidence=0.9,
        probabilities={"yes": 0.9, "no": 0.1},
    )
    assert answer.selected == "yes"


def test_score_answer_structure() -> None:
    answer = ScoreAnswer(
        expected_score=0.5,
        confidence=0.8,
        probabilities={"low": 0.2, "high": 0.8},
    )
    assert answer.expected_score == 0.5


def test_decision_pack_ref_equality() -> None:
    left = DecisionPackRef("pack", "1")
    right = DecisionPackRef("pack", "1")
    assert left == right
