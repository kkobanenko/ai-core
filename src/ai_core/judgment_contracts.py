"""Провайдер-нейтральные типы запроса/ответа Semantic Judgment J1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Union

from ai_core.privacy import DataClass, OutboundForm

# Допуск для суммы вероятностей в ответах choice/score.
PROBABILITY_SUM_TOLERANCE = 1e-5


class QuestionKind(str, Enum):
    """Вариант вопроса в batch-запросе."""

    BINARY = "binary"
    CHOICE = "choice"
    SCORE = "score"


class AnswerKind(str, Enum):
    """Вариант ответа; должен совпадать с вопросом."""

    BINARY = "binary"
    CHOICE = "choice"
    SCORE = "score"


class JudgmentExecutionMode(str, Enum):
    """Явное представление локального vs hosted egress."""

    LOCAL_NO_EGRESS = "local_no_egress"
    HOSTED_EGRESS = "hosted_egress"


@dataclass(frozen=True)
class BinaryQuestion:
    """Бинарный вопрос; порог интерпретации — у потребителя."""

    kind: QuestionKind = QuestionKind.BINARY


@dataclass(frozen=True)
class ChoiceQuestion:
    """Вопрос с конечным набором вариантов."""

    choices: tuple[str, ...]
    kind: QuestionKind = QuestionKind.CHOICE

    def __post_init__(self) -> None:
        if self.kind is not QuestionKind.CHOICE:
            raise ValueError("kind must be CHOICE")
        if not self.choices:
            raise ValueError("choices must be non-empty")
        if len(set(self.choices)) != len(self.choices):
            raise ValueError("choices must be unique")


@dataclass(frozen=True)
class ScoreQuestion:
    """Вопрос со шкалой; уровни задаёт decision pack."""

    levels: tuple[str, ...]
    min_score: float
    max_score: float
    kind: QuestionKind = QuestionKind.SCORE

    def __post_init__(self) -> None:
        if self.kind is not QuestionKind.SCORE:
            raise ValueError("kind must be SCORE")
        if not self.levels:
            raise ValueError("levels must be non-empty")
        if len(set(self.levels)) != len(self.levels):
            raise ValueError("levels must be unique")
        if not _is_finite(self.min_score) or not _is_finite(self.max_score):
            raise ValueError("score bounds must be finite")
        if self.min_score > self.max_score:
            raise ValueError("min_score must be <= max_score")


JudgmentQuestion = Union[BinaryQuestion, ChoiceQuestion, ScoreQuestion]


@dataclass(frozen=True)
class BinaryAnswer:
    """Вероятность «да»; не преобразуем в bool автоматически."""

    probability_true: float
    kind: AnswerKind = AnswerKind.BINARY


@dataclass(frozen=True)
class ChoiceAnswer:
    """Распределение по объявленным вариантам."""

    selected: str
    confidence: float
    probabilities: Mapping[str, float]
    kind: AnswerKind = AnswerKind.CHOICE


@dataclass(frozen=True)
class ScoreAnswer:
    """Ожидаемый score и распределение по уровням."""

    expected_score: float
    confidence: float
    probabilities: Mapping[str, float]
    kind: AnswerKind = AnswerKind.SCORE


JudgmentAnswer = Union[BinaryAnswer, ChoiceAnswer, ScoreAnswer]


@dataclass(frozen=True)
class JudgmentProviderPin:
    """Точный pin провайдера/модели/версии без алиасов latest."""

    provider_id: str
    model: str
    model_version: str


@dataclass(frozen=True)
class DecisionPackRef:
    """Ссылка на decision pack потребителя."""

    decision_pack_id: str
    decision_pack_version: str


@dataclass(frozen=True)
class JudgmentRequest:
    """Batch-first запрос judgment."""

    request_id: str
    decision_pack: DecisionPackRef
    shared_state: Mapping[str, str]
    questions: Mapping[str, JudgmentQuestion]
    provider_pin: JudgmentProviderPin
    execution_mode: JudgmentExecutionMode
    data_class: DataClass
    outbound_form: OutboundForm
    request_egress_authorized: bool
    deadline_monotonic: float


@dataclass(frozen=True)
class JudgmentResponse:
    """Успешный ответ: ровно по одному ответу на каждый вопрос."""

    request_id: str
    decision_pack: DecisionPackRef
    answers: Mapping[str, JudgmentAnswer]
    provider_pin: JudgmentProviderPin
    latency_ms: float
    retry_count: int


def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


__all__ = [
    "PROBABILITY_SUM_TOLERANCE",
    "AnswerKind",
    "BinaryAnswer",
    "BinaryQuestion",
    "ChoiceAnswer",
    "ChoiceQuestion",
    "DecisionPackRef",
    "JudgmentAnswer",
    "JudgmentExecutionMode",
    "JudgmentProviderPin",
    "JudgmentQuestion",
    "JudgmentRequest",
    "JudgmentResponse",
    "QuestionKind",
    "ScoreAnswer",
    "ScoreQuestion",
]
