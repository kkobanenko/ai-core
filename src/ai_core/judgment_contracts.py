"""Вызываемый контракт J1. Пакет вопросов, не разрешение.

Исполняется только репозиторный mock_judgment.
Каталог JUDGMENT этот модуль не пополняет.
Noul не является нейтральным термином ai-core.
TypeSafe Noul в будущем J2 — это только P(true) у BinaryAnswer.
"""

from __future__ import annotations

import json
import math
import re
import threading
import time
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from ai_core.privacy import DataClass, OutboundForm, is_egress_eligible
from ai_core.provider_catalog import NetworkBoundary, UnknownProviderIdentityError, get_provider_identity

# Результат не может выдать эти права. Поля с такими именами запрещены.
FORBIDDEN_AUTHORITY = (
    "merge",
    "deploy",
    "destructive_operation",
    "egress_authorization",
    "access_authorization",
    "automatic_approval",
    "completion_authority",
)
_EXACT_PIN = re.compile(r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*$")
_RESERVED_PIN_PARTS = frozenset({"latest", "x"})
HOSTED_DATA_CLASSES = frozenset({DataClass.SYNTHETIC, DataClass.PUBLIC_NO_PII})
# Имена вопросов, варианты выбора и уровни шкалы.
_MAX_STRING_LENGTH = 128
# Текст инструкции вопроса. Это не идентификатор провайдера.
_MAX_INSTRUCTION_LENGTH = 1024
# Один запрос не несёт безразмерный пакет.
_MAX_QUESTIONS = 32
_MAX_DECLARED_OPTIONS = 32
# Сумма распределения. Неверную сумму не нормализуем.
_DISTRIBUTION_SUM_TOLERANCE = 1e-6
_MAX_PAYLOAD_DEPTH = 32
_MAX_PAYLOAD_NODES = 2048
_MAX_PAYLOAD_STRING_LENGTH = 4096
_MAX_PAYLOAD_KEY_LENGTH = 128
_MAX_CONCURRENT_WORKERS = 16
_WORKER_SEMAPHORE = threading.Semaphore(_MAX_CONCURRENT_WORKERS)
_UNVALIDATED = "unvalidated"

_REQUEST_JSON_KEYS = frozenset(
    {
        "data_class",
        "deadline_monotonic",
        "decision_pack_id",
        "decision_pack_version",
        "hosted_boundary",
        "model",
        "model_version",
        "network_boundary",
        "outbound_form",
        "payload",
        "provider",
        "questions",
        "request_egress_authorized",
        "request_id",
    }
)
_RESPONSE_JSON_KEYS = frozenset(
    {
        "answers",
        "decision_pack_id",
        "decision_pack_version",
        "error",
        "model",
        "model_version",
        "provider",
        "telemetry",
    }
)
_TELEMETRY_JSON_KEYS = frozenset(
    {
        "decision_pack_id",
        "decision_pack_version",
        "error_category",
        "latency_ms",
        "model",
        "model_version",
        "outcome",
        "provider",
        "retry_count",
    }
)
_BINARY_QUESTION_KEYS = frozenset({"kind", "instructions", "true_criterion", "false_criterion"})
_CHOICE_QUESTION_KEYS = frozenset({"kind", "choices"})
_SCORE_QUESTION_KEYS = frozenset({"kind", "levels", "minimum", "maximum"})
_BINARY_ANSWER_KEYS = frozenset({"kind", "probability_true"})
_CHOICE_ANSWER_KEYS = frozenset({"kind", "selected_choice", "confidence", "probabilities"})
_SCORE_ANSWER_KEYS = frozenset({"kind", "expected_score", "confidence", "probabilities"})


class JudgmentErrorCategory(str, Enum):
    """Стабильные категории. Текст провайдера сюда не подставляется."""

    INVALID_REQUEST = "invalid_request"
    PRIVACY_EGRESS_DENIED = "privacy_egress_denied"
    DEADLINE_EXHAUSTED = "deadline_exhausted"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_FAILED = "authentication_failed"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TRANSPORT_FAILED = "transport_failed"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"
    INTERNAL_ERROR = "internal_error"


class JudgmentOutcome(str, Enum):
    """Успешный пакет ответов или ошибка вызова. Нейтрального исхода нет."""

    SUCCESS = "success"
    ERROR = "error"


@dataclass(frozen=True)
class BinaryQuestion:
    """Бинарный вопрос. Порог истины задаёт потребитель, не ai-core."""

    instructions: str
    true_criterion: str | None = None
    false_criterion: str | None = None


@dataclass(frozen=True)
class BinaryAnswer:
    """Вероятность истины. Это не bool и не TypeSafe Noul."""

    probability_true: float


@dataclass(frozen=True)
class ChoiceQuestion:
    """Конечный список объявленных вариантов."""

    choices: tuple[str, ...]


@dataclass(frozen=True)
class ChoiceAnswer:
    """Выбор из объявленного списка и распределение вероятностей."""

    selected_choice: str
    confidence: float
    probabilities: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class ScoreQuestion:
    """Упорядоченные уровни и числовые края шкалы."""

    levels: tuple[str, ...]
    minimum: float
    maximum: float


@dataclass(frozen=True)
class ScoreAnswer:
    """Ожидаемый балл внутри шкалы и распределение по уровням."""

    expected_score: float
    confidence: float
    probabilities: tuple[tuple[str, float], ...]


Question = BinaryQuestion | ChoiceQuestion | ScoreQuestion
Answer = BinaryAnswer | ChoiceAnswer | ScoreAnswer


@dataclass(frozen=True)
class JudgmentTelemetry:
    """Только метаданные. Вопросы, ответы и payload сюда не входят."""

    outcome: JudgmentOutcome
    error_category: JudgmentErrorCategory | None
    latency_ms: int
    retry_count: int
    provider: str
    model: str
    model_version: str
    decision_pack_id: str
    decision_pack_version: str


@dataclass(frozen=True)
class JudgmentRequest:
    """Пакет именованных вопросов над одним состоянием и одним сроком."""

    request_id: str
    decision_pack_id: str
    decision_pack_version: str
    questions: tuple[tuple[str, Question], ...]
    data_class: DataClass
    outbound_form: OutboundForm
    network_boundary: NetworkBoundary
    request_egress_authorized: bool
    hosted_boundary: bool
    deadline_monotonic: float
    provider: str
    model: str
    model_version: str
    payload: object


@dataclass(frozen=True)
class JudgmentResponse:
    """Либо полный набор ответов, либо ошибка вызова. Частичного успеха нет."""

    provider: str
    model: str
    model_version: str
    decision_pack_id: str
    decision_pack_version: str
    telemetry: JudgmentTelemetry
    answers: tuple[tuple[str, Answer], ...] | None = None
    error: JudgmentErrorCategory | None = None


class JudgmentProvider(Protocol):
    """Структурный контракт. Это не TextProvider и не каталог."""

    def judge(self, request: JudgmentRequest) -> JudgmentResponse:
        """Вернуть типизированный ответ. Сеть этим протоколом не задана."""


def invoke_judgment(
    request: JudgmentRequest,
    *,
    mock_behavior: object = None,
    clock: Callable[[], float] = time.monotonic,
    decision_pack_known: Callable[[str, str], bool] | None = None,
) -> JudgmentResponse:
    """Проверить запрос, пакет, приватность, срок, затем выполнить только mock_judgment."""
    guard = _ClockGuard(clock)
    started = guard.read()

    def latency() -> int:
        return _latency_from(started, guard.last)

    if not isinstance(request, JudgmentRequest):
        return _unvalidated_error(JudgmentErrorCategory.INVALID_REQUEST, latency())
    try:
        invalid = _request_error(request)
    except (AttributeError, TypeError, OverflowError, RecursionError, RuntimeError):
        return _unvalidated_error(JudgmentErrorCategory.INVALID_REQUEST, latency())
    if invalid is not None:
        return _unvalidated_error(invalid, latency())
    # В J1 исполняется только репозиторный мок.
    if request.provider != "mock_judgment":
        return _unvalidated_error(JudgmentErrorCategory.INVALID_REQUEST, latency())
    if request.network_boundary is not NetworkBoundary.LOCAL_SAME_HOST or request.hosted_boundary:
        return _unvalidated_error(JudgmentErrorCategory.INVALID_REQUEST, latency())
    if not _privacy_allows(request):
        return _error_response(request, JudgmentErrorCategory.PRIVACY_EGRESS_DENIED, latency())
    if started is None:
        return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, 0)
    dp_now = guard.read()
    if dp_now is None or not _open_at(request, dp_now):
        return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, _latency_from(started, dp_now))
    try:
        dp_ok = _decision_pack_known(request, decision_pack_known, dp_now)
    except FutureTimeoutError:
        timed_out = guard.read()
        if timed_out is None or not _open_at(request, timed_out):
            return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, _latency_from(started, timed_out))
        return _unvalidated_error(JudgmentErrorCategory.INVALID_REQUEST, _latency_from(started, timed_out))
    except Exception:
        return _unvalidated_error(JudgmentErrorCategory.INVALID_REQUEST, latency())
    if not dp_ok:
        return _unvalidated_error(JudgmentErrorCategory.INVALID_REQUEST, latency())
    try:
        from ai_core.judgment_mock import DeterministicMockJudgmentProvider, MockBehavior

        behavior = mock_behavior if isinstance(mock_behavior, MockBehavior) else MockBehavior()
        active = DeterministicMockJudgmentProvider(behavior)
        ready = guard.read()
        if ready is None or not _open_at(request, ready):
            return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, _latency_from(started, ready))
        raw = _judge_within_deadline(active, request, ready)
    except FutureTimeoutError:
        timed_out = guard.read()
        return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, _latency_from(started, timed_out))
    except Exception:
        return _error_response(request, JudgmentErrorCategory.INTERNAL_ERROR, latency())
    try:
        checked = _checked_provider_result(request, raw, 0)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        checked = _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, 0)
    finished = guard.read()
    if finished is None or not _open_at(request, finished):
        return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, _latency_from(started, finished))
    return _with_latency(checked, _latency_from(started, finished))


def request_to_json(request: JudgmentRequest) -> str:
    """Стабильный JSON запроса. Невалидный запрос не сериализуется."""
    if not isinstance(request, JudgmentRequest) or _request_error(request) is not None:
        raise ValueError("request is not a valid J1 contract")
    return json.dumps(_request_document(request), ensure_ascii=True, separators=(",", ":"), sort_keys=True, allow_nan=False)


def request_from_json(text: str) -> JudgmentRequest:
    """Собрать локально валидный запрос. Членство decision-pack здесь не доказывается."""
    loaded = json.loads(text, parse_constant=_reject_json_constant)
    if not isinstance(loaded, dict):
        raise ValueError("request JSON must be an object")
    if set(loaded) != _REQUEST_JSON_KEYS:
        raise ValueError("request JSON fields are not the closed set")
    parsed = JudgmentRequest(
        request_id=_json_str(loaded.get("request_id"), "request_id"),
        decision_pack_id=_json_str(loaded.get("decision_pack_id"), "decision_pack_id"),
        decision_pack_version=_json_str(loaded.get("decision_pack_version"), "decision_pack_version"),
        questions=_json_questions(loaded.get("questions")),
        data_class=DataClass(_json_str(loaded.get("data_class"), "data_class")),
        outbound_form=OutboundForm(_json_str(loaded.get("outbound_form"), "outbound_form")),
        network_boundary=NetworkBoundary(_json_str(loaded.get("network_boundary"), "network_boundary")),
        request_egress_authorized=_json_bool(loaded.get("request_egress_authorized"), "request_egress_authorized"),
        hosted_boundary=_json_bool(loaded.get("hosted_boundary"), "hosted_boundary"),
        deadline_monotonic=_json_number(loaded.get("deadline_monotonic"), "deadline_monotonic"),
        provider=_json_str(loaded.get("provider"), "provider"),
        model=_json_str(loaded.get("model"), "model"),
        model_version=_json_str(loaded.get("model_version"), "model_version"),
        payload=loaded.get("payload"),
    )
    try:
        problem = _request_error(parsed)
    except (AttributeError, TypeError, OverflowError, RuntimeError) as exc:
        raise ValueError("request is not a valid J1 contract") from exc
    if problem is not None:
        raise ValueError("request is not a valid J1 contract")
    return parsed


def response_to_json(response: JudgmentResponse) -> str:
    """Стабильный JSON ответа. Невалидная структура не сериализуется."""
    if _structural_problem(response) is not None:
        raise ValueError("response is not a valid J1 contract")
    return json.dumps(_response_document(response), ensure_ascii=True, separators=(",", ":"), sort_keys=True, allow_nan=False)


def response_from_json(text: str) -> JudgmentResponse:
    """Собрать ответ из JSON. Неверный тип поля не приводится к строке."""
    loaded = json.loads(text, parse_constant=_reject_json_constant)
    if not isinstance(loaded, dict):
        raise ValueError("response JSON must be an object")
    if set(loaded) != _RESPONSE_JSON_KEYS:
        raise ValueError("response JSON fields are not the closed set")
    telemetry_raw = loaded.get("telemetry")
    if not isinstance(telemetry_raw, dict) or set(telemetry_raw) != _TELEMETRY_JSON_KEYS:
        raise ValueError("telemetry must be an object")
    telemetry = JudgmentTelemetry(
        outcome=_json_outcome(telemetry_raw.get("outcome")),
        error_category=_json_error_category(telemetry_raw.get("error_category")),
        latency_ms=_json_int(telemetry_raw.get("latency_ms"), "latency_ms"),
        retry_count=_json_int(telemetry_raw.get("retry_count"), "retry_count"),
        provider=_json_str(telemetry_raw.get("provider"), "provider"),
        model=_json_str(telemetry_raw.get("model"), "model"),
        model_version=_json_str(telemetry_raw.get("model_version"), "model_version"),
        decision_pack_id=_json_str(telemetry_raw.get("decision_pack_id"), "decision_pack_id"),
        decision_pack_version=_json_str(telemetry_raw.get("decision_pack_version"), "decision_pack_version"),
    )
    parsed = JudgmentResponse(
        provider=_json_str(loaded.get("provider"), "provider"),
        model=_json_str(loaded.get("model"), "model"),
        model_version=_json_str(loaded.get("model_version"), "model_version"),
        decision_pack_id=_json_str(loaded.get("decision_pack_id"), "decision_pack_id"),
        decision_pack_version=_json_str(loaded.get("decision_pack_version"), "decision_pack_version"),
        telemetry=telemetry,
        answers=_json_answers(loaded.get("answers")),
        error=_json_error(loaded.get("error")),
    )
    if _structural_problem(parsed) is not None:
        raise ValueError("response is not a valid J1 contract")
    return parsed


def validate_response_for_request(response: object, request: JudgmentRequest) -> JudgmentErrorCategory | None:
    """Проверить ответ относительно запроса. None значит структура пригодна."""
    if not isinstance(response, JudgmentResponse):
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    try:
        checked = _checked_provider_result(request, response, 0)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    return checked.error


def grants_authority(response: JudgmentResponse) -> bool:
    """Контракт не выдаёт права. Истина здесь означает нарушение инварианта."""
    if not isinstance(response, JudgmentResponse) or _structural_problem(response) is not None:
        return False
    document = _response_document(response)
    return any(name in document for name in FORBIDDEN_AUTHORITY)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite constant {value} is not permitted in J1 JSON")


def _request_error(request: JudgmentRequest) -> JudgmentErrorCategory | None:
    if not isinstance(request, JudgmentRequest):
        return JudgmentErrorCategory.INVALID_REQUEST
    names = (
        request.request_id,
        request.decision_pack_id,
        request.decision_pack_version,
        request.provider,
        request.model,
        request.model_version,
    )
    if any(type(item) is not str or len(item) == 0 or len(item) > _MAX_STRING_LENGTH for item in names):
        return JudgmentErrorCategory.INVALID_REQUEST
    if any(not _exact_pin(item) for item in names):
        return JudgmentErrorCategory.INVALID_REQUEST
    if _questions_error(request.questions) is not None:
        return JudgmentErrorCategory.INVALID_REQUEST
    if type(request.request_egress_authorized) is not bool or type(request.hosted_boundary) is not bool:
        return JudgmentErrorCategory.INVALID_REQUEST
    if not isinstance(request.data_class, DataClass) or not isinstance(request.outbound_form, OutboundForm):
        return JudgmentErrorCategory.INVALID_REQUEST
    if not isinstance(request.network_boundary, NetworkBoundary):
        return JudgmentErrorCategory.INVALID_REQUEST
    if type(request.deadline_monotonic) not in (int, float) or not _finite_number(request.deadline_monotonic):
        return JudgmentErrorCategory.INVALID_REQUEST
    if request.payload is not None and not _is_valid_payload_shape(request.payload):
        return JudgmentErrorCategory.INVALID_REQUEST
    if request.hosted_boundary is True and request.network_boundary is not NetworkBoundary.EXTERNAL:
        return JudgmentErrorCategory.INVALID_REQUEST
    return None


def _questions_error(questions: object) -> str | None:
    """Имена уникальны, пакет ограничен, каждый вопрос имеет свой тип."""
    if type(questions) is not tuple:
        return "questions type"
    if len(questions) == 0 or len(questions) > _MAX_QUESTIONS:
        return "questions count"
    seen: set[str] = set()
    for item in questions:
        if type(item) is not tuple or len(item) != 2:
            return "question pair"
        name, question = item
        if type(name) is not str or len(name) == 0 or len(name) > _MAX_STRING_LENGTH:
            return "question name"
        if name in seen:
            return "duplicate question"
        seen.add(name)
        if isinstance(question, BinaryQuestion):
            if _instruction_error(question.instructions) or _optional_text_error(question.true_criterion):
                return "binary question"
            if _optional_text_error(question.false_criterion):
                return "binary question"
        elif isinstance(question, ChoiceQuestion):
            if _option_list_error(question.choices):
                return "choice question"
        elif isinstance(question, ScoreQuestion):
            if _option_list_error(question.levels):
                return "score question"
            if not _finite_number(question.minimum) or not _finite_number(question.maximum):
                return "score scale"
            if question.minimum >= question.maximum:
                return "score scale"
        else:
            return "question type"
    return None


def _instruction_error(value: object) -> bool:
    return type(value) is not str or len(value) == 0 or len(value) > _MAX_INSTRUCTION_LENGTH


def _optional_text_error(value: object) -> bool:
    if value is None:
        return False
    return type(value) is not str or len(value) == 0 or len(value) > _MAX_INSTRUCTION_LENGTH


def _option_list_error(values: object) -> bool:
    if type(values) is not tuple:
        return True
    if len(values) == 0 or len(values) > _MAX_DECLARED_OPTIONS:
        return True
    if len(set(values)) != len(values):
        return True
    return any(type(item) is not str or len(item) == 0 or len(item) > _MAX_STRING_LENGTH for item in values)


def _unit_interval(value: object) -> bool:
    return _finite_number(value) and 0.0 <= float(value) <= 1.0


def _distribution_error(pairs: object, declared: tuple[str, ...]) -> str | None:
    """Ключи совпадают с объявлением. Сумма около 1. Иначе отказ, без нормализации."""
    if type(pairs) is not tuple:
        return "distribution type"
    keys: list[str] = []
    total = 0.0
    for item in pairs:
        if type(item) is not tuple or len(item) != 2:
            return "distribution pair"
        key, probability = item
        if type(key) is not str:
            return "distribution key"
        if not _unit_interval(probability):
            return "distribution value"
        keys.append(key)
        total += float(probability)
    if len(keys) != len(set(keys)) or set(keys) != set(declared):
        return "distribution keys"
    if abs(total - 1.0) > _DISTRIBUTION_SUM_TOLERANCE:
        return "distribution sum"
    return None


def _answer_matches(question: Question, answer: object) -> bool:
    if isinstance(question, BinaryQuestion):
        return isinstance(answer, BinaryAnswer) and _unit_interval(answer.probability_true)
    if isinstance(question, ChoiceQuestion):
        if not isinstance(answer, ChoiceAnswer):
            return False
        if type(answer.selected_choice) is not str or answer.selected_choice not in question.choices:
            return False
        if not _unit_interval(answer.confidence):
            return False
        return _distribution_error(answer.probabilities, question.choices) is None
    if isinstance(question, ScoreQuestion):
        if not isinstance(answer, ScoreAnswer):
            return False
        if not _finite_number(answer.expected_score):
            return False
        if answer.expected_score < question.minimum or answer.expected_score > question.maximum:
            return False
        if not _unit_interval(answer.confidence):
            return False
        return _distribution_error(answer.probabilities, question.levels) is None
    return False


def _checked_provider_result(request: JudgmentRequest, raw: object, latency_ms: int) -> JudgmentResponse:
    if not isinstance(raw, JudgmentResponse):
        return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
    if not _response_identity_ok(raw) or not _identity_matches(request, raw):
        return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
    has_error = raw.error is not None
    has_answers = raw.answers is not None
    if has_error == has_answers:
        return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
    if raw.error is not None:
        if not isinstance(raw.error, JudgmentErrorCategory):
            return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
        return _error_response(request, raw.error, latency_ms)
    if not _answers_match_questions(request, raw.answers):
        return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
    return _success_response(request, raw.answers, latency_ms)


def _answers_match_questions(request: JudgmentRequest, answers: object) -> bool:
    if type(answers) is not tuple or len(answers) != len(request.questions):
        return False
    for (expected_name, question), item in zip(request.questions, answers):
        if type(item) is not tuple or len(item) != 2:
            return False
        name, answer = item
        if name != expected_name or not _answer_matches(question, answer):
            return False
    return True


def _response_identity_ok(raw: JudgmentResponse) -> bool:
    if not _identity_text_ok(raw.provider, raw.model, raw.model_version, raw.decision_pack_id, raw.decision_pack_version):
        return False
    telemetry = raw.telemetry
    if not isinstance(telemetry, JudgmentTelemetry):
        return False
    return _identity_text_ok(
        telemetry.provider,
        telemetry.model,
        telemetry.model_version,
        telemetry.decision_pack_id,
        telemetry.decision_pack_version,
    )


def _identity_matches(request: JudgmentRequest, raw: JudgmentResponse) -> bool:
    return (
        raw.provider == request.provider
        and raw.model == request.model
        and raw.model_version == request.model_version
        and raw.decision_pack_id == request.decision_pack_id
        and raw.decision_pack_version == request.decision_pack_version
        and raw.telemetry.provider == raw.provider
        and raw.telemetry.model == raw.model
        and raw.telemetry.model_version == raw.model_version
        and raw.telemetry.decision_pack_id == raw.decision_pack_id
        and raw.telemetry.decision_pack_version == raw.decision_pack_version
    )


def _identity_text_ok(*values: object) -> bool:
    return all(type(item) is str and _exact_pin(item) for item in values)


def _structural_problem(response: JudgmentResponse) -> str | None:
    if not isinstance(response, JudgmentResponse):
        return "response type"
    if not _response_identity_ok(response):
        return "identity"
    telemetry = response.telemetry
    if not isinstance(telemetry.outcome, JudgmentOutcome):
        return "telemetry outcome type"
    if telemetry.error_category is not None and not isinstance(telemetry.error_category, JudgmentErrorCategory):
        return "telemetry error type"
    if not _nonnegative_int(telemetry.retry_count) or not _nonnegative_int(telemetry.latency_ms):
        return "telemetry range"
    has_error = response.error is not None
    has_answers = response.answers is not None
    if has_error == has_answers:
        return "variant"
    if has_error:
        if not isinstance(response.error, JudgmentErrorCategory):
            return "error type"
        if telemetry.outcome is not JudgmentOutcome.ERROR or telemetry.error_category is not response.error:
            return "telemetry outcome"
        return None
    if telemetry.outcome is not JudgmentOutcome.SUCCESS or telemetry.error_category is not None:
        return "telemetry outcome"
    if type(response.answers) is not tuple:
        return "answers"
    return None


def _privacy_allows(request: JudgmentRequest) -> bool:
    """Мок живёт на локальной границе. Флаг hosted её не расширяет."""
    if request.provider == "mock_judgment":
        boundary = NetworkBoundary.LOCAL_SAME_HOST
    else:
        identity = _governed_identity(request)
        if identity is None:
            return False
        boundary = identity.network_boundary
    if boundary is NetworkBoundary.UNKNOWN_BOUNDARY:
        return False
    eligible = is_egress_eligible(
        data_class=request.data_class,
        outbound_form=request.outbound_form,
        network_boundary=boundary,
        request_egress_authorized=request.request_egress_authorized,
    )
    if eligible is not True:
        return False
    if boundary is NetworkBoundary.EXTERNAL:
        if request.request_egress_authorized is not True:
            return False
        return request.data_class in HOSTED_DATA_CLASSES
    return True


def _governed_identity(request: JudgmentRequest):
    if type(request.provider) is not str:
        return None
    try:
        return get_provider_identity(request.provider)
    except UnknownProviderIdentityError:
        return None


def _decision_pack_known(
    request: JudgmentRequest,
    resolver: Callable[[str, str], bool] | None,
    now: float | None = None,
) -> bool:
    """Резолвер отвечает только «пара id/version известна». Порогов здесь нет."""
    if not callable(resolver):
        return False
    if now is None:
        return False
    try:
        remaining = float(request.deadline_monotonic) - now
    except OverflowError:
        remaining = 0.0
    if remaining <= 0:
        raise FutureTimeoutError()
    known = _run_with_daemon_timeout(
        resolver,
        request.decision_pack_id,
        request.decision_pack_version,
        timeout_seconds=remaining,
    )
    return known is True


def _open_at(request: JudgmentRequest, now: float | None) -> bool:
    if now is None or not _finite_number(request.deadline_monotonic):
        return False
    try:
        deadline = float(request.deadline_monotonic)
    except OverflowError:
        return False
    return now < deadline


def _latency_from(started: float | None, now: float | None) -> int:
    if now is None or started is None:
        return 0
    try:
        elapsed = now - started
        if elapsed < 0 or not math.isfinite(elapsed):
            return 0
        val = elapsed * 1000
        if not math.isfinite(val) or val > 2147483647:
            return 2147483647
        return int(val)
    except (OverflowError, ValueError, TypeError):
        return 0


def _run_with_daemon_timeout(func: Callable, *args: object, timeout_seconds: float) -> object:
    """Выполнить функцию в daemon-потоке. Ожидание не длиннее остатка срока."""
    if timeout_seconds <= 0:
        raise FutureTimeoutError()
    start_wait = time.monotonic()
    acquired = _WORKER_SEMAPHORE.acquire(blocking=True, timeout=timeout_seconds)
    if not acquired:
        raise FutureTimeoutError()
    wait_elapsed = time.monotonic() - start_wait
    remaining = timeout_seconds - wait_elapsed
    if remaining <= 0:
        _WORKER_SEMAPHORE.release()
        raise FutureTimeoutError()
    future: Future = Future()

    def worker() -> None:
        try:
            res = func(*args)
            if not future.done():
                future.set_result(res)
        except BaseException as exc:
            if not future.done():
                future.set_exception(exc)
        finally:
            _WORKER_SEMAPHORE.release()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return future.result(timeout=remaining)


def _judge_within_deadline(active: JudgmentProvider, request: JudgmentRequest, now: float) -> object:
    try:
        remaining = float(request.deadline_monotonic) - now
    except OverflowError:
        remaining = 0.0
    if remaining <= 0:
        raise FutureTimeoutError()
    return _run_with_daemon_timeout(active.judge, request, timeout_seconds=remaining)


def _with_latency(response: JudgmentResponse, latency_ms: int) -> JudgmentResponse:
    telemetry = response.telemetry
    stamped = JudgmentTelemetry(
        telemetry.outcome,
        telemetry.error_category,
        latency_ms,
        telemetry.retry_count,
        telemetry.provider,
        telemetry.model,
        telemetry.model_version,
        telemetry.decision_pack_id,
        telemetry.decision_pack_version,
    )
    return JudgmentResponse(
        provider=response.provider,
        model=response.model,
        model_version=response.model_version,
        decision_pack_id=response.decision_pack_id,
        decision_pack_version=response.decision_pack_version,
        telemetry=stamped,
        answers=response.answers,
        error=response.error,
    )


def _success_response(request: JudgmentRequest, answers: tuple[tuple[str, Answer], ...], latency_ms: int) -> JudgmentResponse:
    telemetry = _telemetry(request, JudgmentOutcome.SUCCESS, None, latency_ms)
    return JudgmentResponse(
        provider=request.provider,
        model=request.model,
        model_version=request.model_version,
        decision_pack_id=request.decision_pack_id,
        decision_pack_version=request.decision_pack_version,
        telemetry=telemetry,
        answers=answers,
        error=None,
    )


def _error_response(request: JudgmentRequest, category: JudgmentErrorCategory, latency_ms: int) -> JudgmentResponse:
    telemetry = _telemetry(request, JudgmentOutcome.ERROR, category, latency_ms)
    return JudgmentResponse(
        provider=request.provider,
        model=request.model,
        model_version=request.model_version,
        decision_pack_id=request.decision_pack_id,
        decision_pack_version=request.decision_pack_version,
        telemetry=telemetry,
        answers=None,
        error=category,
    )


def _unvalidated_error(category: JudgmentErrorCategory, latency_ms: int) -> JudgmentResponse:
    telemetry = JudgmentTelemetry(
        outcome=JudgmentOutcome.ERROR,
        error_category=category,
        latency_ms=latency_ms,
        retry_count=0,
        provider=_UNVALIDATED,
        model=_UNVALIDATED,
        model_version=_UNVALIDATED,
        decision_pack_id=_UNVALIDATED,
        decision_pack_version=_UNVALIDATED,
    )
    return JudgmentResponse(
        provider=_UNVALIDATED,
        model=_UNVALIDATED,
        model_version=_UNVALIDATED,
        decision_pack_id=_UNVALIDATED,
        decision_pack_version=_UNVALIDATED,
        telemetry=telemetry,
        answers=None,
        error=category,
    )


def _telemetry(
    request: JudgmentRequest,
    outcome: JudgmentOutcome,
    category: JudgmentErrorCategory | None,
    latency_ms: int,
) -> JudgmentTelemetry:
    return JudgmentTelemetry(
        outcome=outcome,
        error_category=category,
        latency_ms=latency_ms,
        retry_count=0,
        provider=request.provider,
        model=request.model,
        model_version=request.model_version,
        decision_pack_id=request.decision_pack_id,
        decision_pack_version=request.decision_pack_version,
    )


def _is_valid_payload_shape(value: object) -> bool:
    if value is None:
        return True
    seen_ids: set[int] = set()
    node_count = 0

    def _check(item: object, depth: int) -> bool:
        nonlocal node_count
        node_count += 1
        if node_count > _MAX_PAYLOAD_NODES or depth > _MAX_PAYLOAD_DEPTH:
            return False
        if item is None or type(item) is bool:
            return True
        if type(item) is str:
            return len(item) <= _MAX_PAYLOAD_STRING_LENGTH
        if type(item) is int:
            return item.bit_length() <= 1023
        if type(item) is float:
            return math.isfinite(item)
        if type(item) is list:
            item_id = id(item)
            if item_id in seen_ids:
                return False
            seen_ids.add(item_id)
            try:
                return all(_check(elem, depth + 1) for elem in item)
            finally:
                seen_ids.remove(item_id)
        if type(item) is dict:
            item_id = id(item)
            if item_id in seen_ids:
                return False
            seen_ids.add(item_id)
            try:
                for key, inner in item.items():
                    if type(key) is not str or len(key) == 0 or len(key) > _MAX_PAYLOAD_KEY_LENGTH:
                        return False
                    if not _check(inner, depth + 1):
                        return False
                return True
            finally:
                seen_ids.remove(item_id)
        return False

    try:
        return _check(value, 0)
    except (RecursionError, OverflowError):
        return False


def _finite_number(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        if type(value) is int:
            return value.bit_length() <= 1023
        return math.isfinite(value)
    except Exception:
        return False


def _nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _exact_pin(value: object) -> bool:
    if type(value) is not str or len(value) == 0 or len(value) > _MAX_STRING_LENGTH:
        return False
    if _EXACT_PIN.fullmatch(value) is None:
        return False
    parts = re.split(r"[._-]", value)
    return all(part.lower() not in _RESERVED_PIN_PARTS for part in parts)


def _json_str(value: object, name: str) -> str:
    if type(value) is not str or len(value) == 0 or len(value) > _MAX_STRING_LENGTH:
        raise ValueError(f"{name} must be a bounded string")
    return value


def _json_bool(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a bool")
    return value


def _json_number(value: object, name: str) -> float:
    if not _finite_number(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)  # type: ignore[arg-type]


def _json_int(value: object, name: str) -> int:
    if not _nonnegative_int(value):
        raise ValueError(f"{name} must be a non-negative int")
    return value  # type: ignore[return-value]


def _json_outcome(value: object) -> JudgmentOutcome:
    if type(value) is not str:
        raise ValueError("outcome must be a string")
    try:
        return JudgmentOutcome(value)
    except ValueError as exc:
        raise ValueError("outcome is outside the closed set") from exc


def _json_error_category(value: object) -> JudgmentErrorCategory | None:
    if value is None:
        return None
    if type(value) is not str:
        raise ValueError("error_category must be a string")
    try:
        return JudgmentErrorCategory(value)
    except ValueError as exc:
        raise ValueError("error_category is outside the closed set") from exc


def _json_error(value: object) -> JudgmentErrorCategory | None:
    if value is None:
        return None
    return JudgmentErrorCategory(_json_str(value, "error"))


def _json_questions(value: object) -> tuple[tuple[str, Question], ...]:
    if type(value) is not dict:
        raise ValueError("questions must be an object")
    if len(value) == 0 or len(value) > _MAX_QUESTIONS:
        raise ValueError("questions count is outside the bound")
    pairs: list[tuple[str, Question]] = []
    for name in sorted(value):
        if type(name) is not str:
            raise ValueError("question name must be a string")
        pairs.append((name, _json_question(value[name])))
    return tuple(pairs)


def _json_question(value: object) -> Question:
    if type(value) is not dict or "kind" not in value:
        raise ValueError("question must declare kind")
    kind = value.get("kind")
    if kind == "binary":
        if set(value) != _BINARY_QUESTION_KEYS:
            raise ValueError("binary question fields are not the closed set")
        return BinaryQuestion(
            instructions=_json_instruction(value.get("instructions"), "instructions"),
            true_criterion=_json_optional_text(value.get("true_criterion"), "true_criterion"),
            false_criterion=_json_optional_text(value.get("false_criterion"), "false_criterion"),
        )
    if kind == "choice":
        if set(value) != _CHOICE_QUESTION_KEYS:
            raise ValueError("choice question fields are not the closed set")
        return ChoiceQuestion(choices=_json_options(value.get("choices"), "choices"))
    if kind == "score":
        if set(value) != _SCORE_QUESTION_KEYS:
            raise ValueError("score question fields are not the closed set")
        return ScoreQuestion(
            levels=_json_options(value.get("levels"), "levels"),
            minimum=_json_number(value.get("minimum"), "minimum"),
            maximum=_json_number(value.get("maximum"), "maximum"),
        )
    raise ValueError("question kind is outside the closed set")


def _json_instruction(value: object, name: str) -> str:
    if type(value) is not str or len(value) == 0 or len(value) > _MAX_INSTRUCTION_LENGTH:
        raise ValueError(f"{name} must be a bounded instruction")
    return value


def _json_optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _json_instruction(value, name)


def _json_options(value: object, name: str) -> tuple[str, ...]:
    if type(value) is not list:
        raise ValueError(f"{name} must be a list")
    if any(type(item) is not str for item in value):
        raise ValueError(f"{name} must be a list of strings")
    return tuple(value)


def _json_answers(value: object) -> tuple[tuple[str, Answer], ...] | None:
    if value is None:
        return None
    if type(value) is not dict:
        raise ValueError("answers must be an object")
    pairs: list[tuple[str, Answer]] = []
    for name in sorted(value):
        if type(name) is not str:
            raise ValueError("answer name must be a string")
        pairs.append((name, _json_answer(value[name])))
    return tuple(pairs)


def _json_answer(value: object) -> Answer:
    if type(value) is not dict or "kind" not in value:
        raise ValueError("answer must declare kind")
    kind = value.get("kind")
    if kind == "binary":
        if set(value) != _BINARY_ANSWER_KEYS:
            raise ValueError("binary answer fields are not the closed set")
        return BinaryAnswer(probability_true=_json_number(value.get("probability_true"), "probability_true"))
    if kind == "choice":
        if set(value) != _CHOICE_ANSWER_KEYS:
            raise ValueError("choice answer fields are not the closed set")
        return ChoiceAnswer(
            selected_choice=_json_str(value.get("selected_choice"), "selected_choice"),
            confidence=_json_number(value.get("confidence"), "confidence"),
            probabilities=_json_probability_pairs(value.get("probabilities")),
        )
    if kind == "score":
        if set(value) != _SCORE_ANSWER_KEYS:
            raise ValueError("score answer fields are not the closed set")
        return ScoreAnswer(
            expected_score=_json_number(value.get("expected_score"), "expected_score"),
            confidence=_json_number(value.get("confidence"), "confidence"),
            probabilities=_json_probability_pairs(value.get("probabilities")),
        )
    raise ValueError("answer kind is outside the closed set")


def _json_probability_pairs(value: object) -> tuple[tuple[str, float], ...]:
    if type(value) is not dict:
        raise ValueError("probabilities must be an object")
    pairs: list[tuple[str, float]] = []
    for key in value:
        if type(key) is not str:
            raise ValueError("probability key must be a string")
        pairs.append((key, _json_number(value[key], "probability")))
    return tuple(pairs)


def _request_document(request: JudgmentRequest) -> dict:
    questions = {name: _question_document(question) for name, question in request.questions}
    return {
        "data_class": request.data_class.value,
        "deadline_monotonic": request.deadline_monotonic,
        "decision_pack_id": request.decision_pack_id,
        "decision_pack_version": request.decision_pack_version,
        "hosted_boundary": request.hosted_boundary,
        "model": request.model,
        "model_version": request.model_version,
        "network_boundary": request.network_boundary.value,
        "outbound_form": request.outbound_form.value,
        "payload": request.payload,
        "provider": request.provider,
        "questions": questions,
        "request_egress_authorized": request.request_egress_authorized,
        "request_id": request.request_id,
    }


def _question_document(question: Question) -> dict:
    if isinstance(question, BinaryQuestion):
        return {
            "kind": "binary",
            "instructions": question.instructions,
            "true_criterion": question.true_criterion,
            "false_criterion": question.false_criterion,
        }
    if isinstance(question, ChoiceQuestion):
        return {"kind": "choice", "choices": list(question.choices)}
    return {
        "kind": "score",
        "levels": list(question.levels),
        "minimum": question.minimum,
        "maximum": question.maximum,
    }


def _response_document(response: JudgmentResponse) -> dict:
    answers = None
    if response.answers is not None:
        answers = {name: _answer_document(answer) for name, answer in response.answers}
    return {
        "answers": answers,
        "decision_pack_id": response.decision_pack_id,
        "decision_pack_version": response.decision_pack_version,
        "error": None if response.error is None else response.error.value,
        "model": response.model,
        "model_version": response.model_version,
        "provider": response.provider,
        "telemetry": {
            "decision_pack_id": response.telemetry.decision_pack_id,
            "decision_pack_version": response.telemetry.decision_pack_version,
            "error_category": None if response.telemetry.error_category is None else response.telemetry.error_category.value,
            "latency_ms": response.telemetry.latency_ms,
            "model": response.telemetry.model,
            "model_version": response.telemetry.model_version,
            "outcome": response.telemetry.outcome.value,
            "provider": response.telemetry.provider,
            "retry_count": response.telemetry.retry_count,
        },
    }


def _answer_document(answer: Answer) -> dict:
    if isinstance(answer, BinaryAnswer):
        return {"kind": "binary", "probability_true": answer.probability_true}
    if isinstance(answer, ChoiceAnswer):
        return {
            "kind": "choice",
            "selected_choice": answer.selected_choice,
            "confidence": answer.confidence,
            "probabilities": {key: value for key, value in answer.probabilities},
        }
    return {
        "kind": "score",
        "expected_score": answer.expected_score,
        "confidence": answer.confidence,
        "probabilities": {key: value for key, value in answer.probabilities},
    }


class _ClockGuard:
    """Часы одного вызова. Следующий отсчёт не может быть меньше предыдущего."""

    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self.last: float | None = None

    def read(self) -> float | None:
        sample = _safe_now(self._clock)
        if sample is None:
            return None
        if self.last is not None and sample < self.last:
            return None
        self.last = sample
        return sample


def _safe_now(clock: Callable[[], float]) -> float | None:
    try:
        value = clock()
    except Exception:
        return None
    if not _finite_number(value):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except OverflowError:
        return None
