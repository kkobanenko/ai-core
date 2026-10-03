"""Вызываемый контракт J1. Это улика, не разрешение.

Провайдер здесь не выбирается и не ходит в сеть.
Живой каталог JUDGMENT этот модуль не пополняет.
"""

from __future__ import annotations

import json
import math
import re
import time
import threading
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
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
# Полное совпадение. Буква, цифра, точка, дефис и подчёркивание. Не селектор.
_EXACT_PIN = re.compile(r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*$")
_RESERVED_PIN_PARTS = frozenset({"latest", "x"})
HOSTED_DATA_CLASSES = frozenset({DataClass.SYNTHETIC, DataClass.PUBLIC_NO_PII})


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


class NoulReason(str, Enum):
    """Закрытый код отказа. Свободный текст провайдера сюда не входит."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    AMBIGUOUS_INPUT = "ambiguous_input"
    UNSUPPORTED_CRITERION = "unsupported_criterion"
    NO_RELIABLE_JUDGMENT = "no_reliable_judgment"


class JudgmentOutcome(str, Enum):
    """Закрытый исход телеметрии. Свободный текст сюда не входит."""

    CHOICE = "choice"
    NOUL = "noul"
    ERROR = "error"


_UNVALIDATED = "unvalidated"
_REQUEST_JSON_KEYS = frozenset(
    {
        "allowed_choices",
        "criterion_id",
        "data_class",
        "deadline_monotonic",
        "decision_pack_id",
        "decision_pack_version",
        "hosted_boundary",
        "model",
        "model_version",
        "network_boundary",
        "noul_allowed",
        "outbound_form",
        "payload",
        "provider",
        "request_egress_authorized",
        "request_id",
        "score_scale",
    }
)
_RESPONSE_JSON_KEYS = frozenset(
    {
        "choice",
        "decision_pack_id",
        "decision_pack_version",
        "error",
        "model",
        "model_version",
        "noul",
        "provider",
        "score",
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


@dataclass(frozen=True)
class Choice:
    """Один символический исход. Смысл задаёт потребитель, не ai-core."""

    value: str


@dataclass(frozen=True)
class ScoreScale:
    """Объявленная шкала. Число само по себе ничего не разрешает."""

    score_id: str
    minimum: float
    maximum: float


@dataclass(frozen=True)
class Score:
    """Оценка внутри объявленной шкалы."""

    score_id: str
    value: float


@dataclass(frozen=True)
class Noul:
    """Провайдер не смог дать пригодное суждение. Скрытого Choice здесь нет."""

    reason_code: NoulReason


@dataclass(frozen=True)
class JudgmentTelemetry:
    """Только метаданные. Полезная нагрузка и секреты сюда не входят."""

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
    """Неизменяемый запрос. Часы и провайдер в него не входят."""

    request_id: str
    decision_pack_id: str
    decision_pack_version: str
    criterion_id: str
    allowed_choices: tuple[str, ...]
    noul_allowed: bool
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
    score_scale: ScoreScale | None = None


@dataclass(frozen=True)
class JudgmentResponse:
    """Ровно один вариант: choice, noul или error."""

    provider: str
    model: str
    model_version: str
    decision_pack_id: str
    decision_pack_version: str
    telemetry: JudgmentTelemetry
    choice: Choice | None = None
    score: Score | None = None
    noul: Noul | None = None
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
    """Проверить запрос, пакет, приватность, срок, затем выполнить детерминированный мок.

    В J1 разрешено исполнение ТОЛЬКО репозиторного детерминированного мока mock_judgment.
    Исполнение реальных провайдеров и фабрик запрещено до авторизации J2 и допуска JUDGMENT.
    """
    started = _safe_now(clock)
    if not isinstance(request, JudgmentRequest):
        return _unvalidated_error(JudgmentErrorCategory.INVALID_REQUEST, _safe_latency(started, clock))
    try:
        invalid = _request_error(request)
    except (AttributeError, TypeError, OverflowError, RecursionError):
        return _unvalidated_error(JudgmentErrorCategory.INVALID_REQUEST, _safe_latency(started, clock))
    if invalid is not None:
        return _unvalidated_error(invalid, _safe_latency(started, clock))
    # В J1 callable execution path разрешён только mock_judgment
    if request.provider != "mock_judgment":
        return _unvalidated_error(JudgmentErrorCategory.INVALID_REQUEST, _safe_latency(started, clock))
    # mock_judgment имеет фиксированную доверенную границу LOCAL_SAME_HOST без hosted_boundary
    if request.network_boundary is not NetworkBoundary.LOCAL_SAME_HOST or request.hosted_boundary:
        return _unvalidated_error(JudgmentErrorCategory.INVALID_REQUEST, _safe_latency(started, clock))
    # Привратник приватности проверяется ДО обращения к резолверу decision-pack
    if not _privacy_allows(request):
        return _error_response(request, JudgmentErrorCategory.PRIVACY_EGRESS_DENIED, _safe_latency(started, clock))
    dp_now = _safe_now(clock)
    if not _open_at(request, dp_now):
        return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, _latency_from(started, dp_now))
    try:
        dp_ok = _decision_pack_known(request, decision_pack_known, dp_now)
    except FutureTimeoutError:
        timed_out = _safe_now(clock)
        return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, _latency_from(started, timed_out))
    except Exception:
        dp_ok = False
    if not dp_ok:
        return _unvalidated_error(JudgmentErrorCategory.INVALID_REQUEST, _safe_latency(started, clock))
    try:
        from ai_core.judgment_mock import DeterministicMockJudgmentProvider, MockBehavior
        behavior = mock_behavior if isinstance(mock_behavior, MockBehavior) else MockBehavior()
        active = DeterministicMockJudgmentProvider(behavior)
        ready = _safe_now(clock)
        if not _open_at(request, ready):
            return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, _latency_from(started, ready))
        raw = _judge_within_deadline(active, request, ready)
    except FutureTimeoutError:
        timed_out = _safe_now(clock)
        return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, _latency_from(started, timed_out))
    except Exception:
        return _error_response(request, JudgmentErrorCategory.INTERNAL_ERROR, _safe_latency(started, clock))
    try:
        checked = _checked_provider_result(request, raw, 0)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        checked = _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, 0)
    finished = _safe_now(clock)
    latency = _latency_from(started, finished)
    if not _open_at(request, finished):
        return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, latency)
    return _with_latency(checked, latency)


def request_to_json(request: JudgmentRequest) -> str:
    """Стабильный JSON запроса. Невалидный запрос не сериализуется."""
    if not isinstance(request, JudgmentRequest) or _request_error(request) is not None:
        raise ValueError("request is not a valid J1 contract")
    return json.dumps(_request_document(request), ensure_ascii=True, separators=(",", ":"), sort_keys=True, allow_nan=False)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite constant {value} is not permitted in J1 JSON")


def request_from_json(text: str) -> JudgmentRequest:
    """Собрать локально валидный запрос из JSON.

    Членство decision-pack в доверенных метаданных потребителя здесь не доказывается.
    Его проверяет invoke_judgment через decision_pack_known.
    """
    loaded = json.loads(text, parse_constant=_reject_json_constant)
    if not isinstance(loaded, dict):
        raise ValueError("request JSON must be an object")
    if set(loaded) != _REQUEST_JSON_KEYS:
        raise ValueError("request JSON fields are not the closed set")
    choices = loaded.get("allowed_choices")
    if not isinstance(choices, list) or len(choices) == 0 or len(choices) > _MAX_ALLOWED_CHOICES:
        raise ValueError("allowed_choices must be a bounded non-empty list of strings")
    if any(type(item) is not str or len(item) == 0 or len(item) > _MAX_STRING_LENGTH for item in choices):
        raise ValueError("allowed_choices must be a list of bounded non-empty strings")
    parsed = JudgmentRequest(
        request_id=_json_str(loaded.get("request_id"), "request_id"),
        decision_pack_id=_json_str(loaded.get("decision_pack_id"), "decision_pack_id"),
        decision_pack_version=_json_str(loaded.get("decision_pack_version"), "decision_pack_version"),
        criterion_id=_json_str(loaded.get("criterion_id"), "criterion_id"),
        allowed_choices=tuple(choices),
        noul_allowed=_json_bool(loaded.get("noul_allowed"), "noul_allowed"),
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
        score_scale=_json_scale(loaded.get("score_scale")),
    )
    try:
        problem = _request_error(parsed)
    except (AttributeError, TypeError, OverflowError) as exc:
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
        choice=_json_choice(loaded.get("choice")),
        score=_json_score(loaded.get("score")),
        noul=_json_noul(loaded.get("noul")),
        error=_json_error(loaded.get("error")),
    )
    if _structural_problem(parsed) is not None:
        raise ValueError("response JSON violates the J1 contract")
    return parsed


def validate_response_for_request(response: JudgmentResponse, request: JudgmentRequest) -> JudgmentErrorCategory | None:
    """Сначала структура ответа. Потом сверка с запросом."""
    if not isinstance(response, JudgmentResponse) or _structural_problem(response) is not None:
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    try:
        request_problem = _request_error(request)
    except (AttributeError, TypeError):
        return JudgmentErrorCategory.INVALID_REQUEST
    if request_problem is not None:
        return JudgmentErrorCategory.INVALID_REQUEST
    if not _identity_matches(request, response):
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    if response.error is not None:
        return None
    if response.noul is not None:
        if request.noul_allowed is not True:
            return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
        return None
    if response.choice is None or type(response.choice.value) is not str or not _exact_pin(response.choice.value) or response.choice.value not in request.allowed_choices:
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    return _score_error(request, response.score)


def _structural_problem(response: JudgmentResponse) -> str | None:
    """Инварианты ответа без знания запроса."""
    if not isinstance(response, JudgmentResponse):
        return "response type"
    if not _identity_text_ok(
        response.provider,
        response.model,
        response.model_version,
        response.decision_pack_id,
        response.decision_pack_version,
    ):
        return "identity"
    if response.choice is not None and not isinstance(response.choice, Choice):
        return "choice type"
    if response.score is not None and not isinstance(response.score, Score):
        return "score type"
    if response.noul is not None and not isinstance(response.noul, Noul):
        return "noul type"
    if response.error is not None and not isinstance(response.error, JudgmentErrorCategory):
        return "error type"
    present = (
        response.choice is not None,
        response.noul is not None,
        response.error is not None,
    )
    if sum(1 for item in present if item) != 1:
        return "variant count"
    if response.choice is not None and (type(response.choice.value) is not str or not _exact_pin(response.choice.value)):
        return "choice value"
    if response.noul is not None and not isinstance(response.noul.reason_code, NoulReason):
        return "noul reason"
    if response.score is not None:
        if response.choice is None or not _score_shape_ok(response.score):
            return "score"
    if response.error is not None and response.score is not None:
        return "score with error"
    telemetry = response.telemetry
    if not isinstance(telemetry, JudgmentTelemetry):
        return "telemetry"
    if not isinstance(telemetry.outcome, JudgmentOutcome):
        return "telemetry outcome type"
    if telemetry.error_category is not None and not isinstance(telemetry.error_category, JudgmentErrorCategory):
        return "telemetry error type"
    if not _identity_text_ok(
        telemetry.provider,
        telemetry.model,
        telemetry.model_version,
        telemetry.decision_pack_id,
        telemetry.decision_pack_version,
    ):
        return "telemetry identity"
    if not _nonnegative_int(telemetry.retry_count) or not _nonnegative_int(telemetry.latency_ms):
        return "telemetry range"
    if (
        telemetry.provider != response.provider
        or telemetry.model != response.model
        or telemetry.model_version != response.model_version
        or telemetry.decision_pack_id != response.decision_pack_id
        or telemetry.decision_pack_version != response.decision_pack_version
    ):
        return "telemetry identity"
    if response.choice is not None:
        if telemetry.outcome is not JudgmentOutcome.CHOICE or telemetry.error_category is not None:
            return "telemetry outcome"
    elif response.noul is not None:
        if telemetry.outcome is not JudgmentOutcome.NOUL or telemetry.error_category is not None:
            return "telemetry outcome"
    elif telemetry.outcome is not JudgmentOutcome.ERROR or telemetry.error_category is not response.error:
        return "telemetry outcome"
    return None


def _score_shape_ok(score: Score) -> bool:
    if not isinstance(score.score_id, str) or not _exact_pin(score.score_id):
        return False
    return _finite_number(score.value)


def grants_authority(response: JudgmentResponse) -> bool:
    """Контракт не выдаёт права. Истина здесь означает нарушение инварианта."""
    if not isinstance(response, JudgmentResponse) or _structural_problem(response) is not None:
        return False
    document = _response_document(response)
    return any(name in document for name in FORBIDDEN_AUTHORITY)


def _json_outcome(value: object) -> JudgmentOutcome:
    if not isinstance(value, str):
        raise ValueError("outcome must be a string")
    try:
        return JudgmentOutcome(value)
    except ValueError as exc:
        raise ValueError("outcome is outside the closed set") from exc


def _json_error_category(value: object) -> JudgmentErrorCategory | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("error_category must be a string")
    try:
        return JudgmentErrorCategory(value)
    except ValueError as exc:
        raise ValueError("error_category is outside the closed set") from exc


def _json_str(value: object, name: str) -> str:
    if type(value) is not str or value.strip() == "" or len(value) > _MAX_STRING_LENGTH:
        raise ValueError(f"{name} must be a non-empty string under {_MAX_STRING_LENGTH} characters")
    return value


def _json_text(value: object, name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{name} must be a string")
    return value


def _json_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _json_number(value: object, name: str) -> float:
    if not _finite_number(value):
        raise ValueError(f"{name} must be a finite number")
    try:
        return float(value)  # type: ignore[arg-type]
    except OverflowError as exc:
        raise ValueError(f"{name} must be a finite number") from exc


def _json_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _json_scale(value: object) -> ScoreScale | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("score_scale must be an object")
    if set(value.keys()) != {"score_id", "minimum", "maximum"}:
        raise ValueError("score_scale must only contain score_id, minimum, and maximum")
    return ScoreScale(
        score_id=_json_str(value.get("score_id"), "score_id"),
        minimum=_json_number(value.get("minimum"), "minimum"),
        maximum=_json_number(value.get("maximum"), "maximum"),
    )


def _json_choice(value: object) -> Choice | None:
    if value is None:
        return None
    return Choice(_json_str(value, "choice"))


def _json_score(value: object) -> Score | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("score must be an object")
    if set(value.keys()) != {"score_id", "value"}:
        raise ValueError("score must only contain score_id and value")
    return Score(score_id=_json_str(value.get("score_id"), "score_id"), value=_json_number(value.get("value"), "value"))


def _json_noul(value: object) -> Noul | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("noul must be a string")
    try:
        reason = NoulReason(value)
    except ValueError as exc:
        raise ValueError("noul reason is outside the closed set") from exc
    return Noul(reason)


def _json_error(value: object) -> JudgmentErrorCategory | None:
    if value is None:
        return None
    return JudgmentErrorCategory(_json_str(value, "error"))


_MAX_STRING_LENGTH = 128
_MAX_ALLOWED_CHOICES = 128


def _request_error(request: JudgmentRequest) -> JudgmentErrorCategory | None:
    if not isinstance(request, JudgmentRequest):
        return JudgmentErrorCategory.INVALID_REQUEST
    names = (
        request.request_id,
        request.decision_pack_id,
        request.decision_pack_version,
        request.criterion_id,
        request.provider,
        request.model,
        request.model_version,
    )
    if any(type(item) is not str or len(item) == 0 or len(item) > _MAX_STRING_LENGTH for item in names):
        return JudgmentErrorCategory.INVALID_REQUEST
    if any(not _exact_pin(item) for item in names):
        return JudgmentErrorCategory.INVALID_REQUEST
    choices = request.allowed_choices
    if not isinstance(choices, tuple):
        return JudgmentErrorCategory.INVALID_REQUEST
    if len(choices) == 0 or len(choices) > _MAX_ALLOWED_CHOICES or len(set(choices)) != len(choices):
        return JudgmentErrorCategory.INVALID_REQUEST
    if any(type(item) is not str or len(item) == 0 or len(item) > _MAX_STRING_LENGTH for item in choices):
        return JudgmentErrorCategory.INVALID_REQUEST
    if any(not _exact_pin(item) for item in choices):
        return JudgmentErrorCategory.INVALID_REQUEST
    if not isinstance(request.noul_allowed, bool):
        return JudgmentErrorCategory.INVALID_REQUEST
    if not isinstance(request.request_egress_authorized, bool) or not isinstance(request.hosted_boundary, bool):
        return JudgmentErrorCategory.INVALID_REQUEST
    if not isinstance(request.data_class, DataClass) or not isinstance(request.outbound_form, OutboundForm):
        return JudgmentErrorCategory.INVALID_REQUEST
    if not isinstance(request.network_boundary, NetworkBoundary):
        return JudgmentErrorCategory.INVALID_REQUEST
    if not isinstance(request.deadline_monotonic, (int, float)) or isinstance(request.deadline_monotonic, bool):
        return JudgmentErrorCategory.INVALID_REQUEST
    if not _finite_number(request.deadline_monotonic):
        return JudgmentErrorCategory.INVALID_REQUEST
    if request.score_scale is not None and not _scale_ok(request.score_scale):
        return JudgmentErrorCategory.INVALID_REQUEST
    if request.payload is not None and not _is_valid_payload_shape(request.payload):
        return JudgmentErrorCategory.INVALID_REQUEST
    # Флаг hosted не может объявить внешнюю границу локальной.
    if request.hosted_boundary is True and request.network_boundary is not NetworkBoundary.EXTERNAL:
        return JudgmentErrorCategory.INVALID_REQUEST
    return None


_MAX_PAYLOAD_DEPTH = 32
_MAX_PAYLOAD_NODES = 2048


def _is_valid_payload_shape(value: object) -> bool:
    """Проверка, что payload является ограниченным ацикличным JSON-деревом без нестандартных типов и NaN/Inf."""
    if value is None:
        return True
    seen_ids: set[int] = set()
    node_count = 0

    def _check(item: object, depth: int) -> bool:
        nonlocal node_count
        node_count += 1
        if node_count > _MAX_PAYLOAD_NODES:
            return False
        if depth > _MAX_PAYLOAD_DEPTH:
            return False
        if item is None:
            return True
        if type(item) is bool:
            return True
        if type(item) is str:
            return True
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
                for elem in item:
                    if not _check(elem, depth + 1):
                        return False
            finally:
                seen_ids.remove(item_id)
            return True
        if type(item) is dict:
            item_id = id(item)
            if item_id in seen_ids:
                return False
            seen_ids.add(item_id)
            try:
                for k, v in item.items():
                    if type(k) is not str:
                        return False
                    if not _check(v, depth + 1):
                        return False
            finally:
                seen_ids.remove(item_id)
            return True
        return False

    try:
        return _check(value, 0)
    except (RecursionError, OverflowError):
        return False


def _scale_ok(scale: object) -> bool:
    if not isinstance(scale, ScoreScale):
        return False
    if type(scale.score_id) is not str or not _exact_pin(scale.score_id):
        return False
    if not _finite_number(scale.minimum) or not _finite_number(scale.maximum):
        return False
    return scale.minimum < scale.maximum


def _finite_number(value: object) -> bool:
    """Конечное число точного типа int или float без hostile overrides."""
    if type(value) not in (int, float):
        return False
    try:
        if type(value) is int:
            if value.bit_length() > 1023:
                return False
            return True
        return math.isfinite(value)
    except Exception:
        return False


def _nonnegative_int(value: object) -> bool:
    """Сначала тип. Потом знак. bool не является счётчиком."""
    if type(value) is not int:
        return False
    return value >= 0


def _exact_pin(value: object) -> bool:
    """Точный литерал на всю строку. Селектор не проходит."""
    if type(value) is not str:
        return False
    if len(value) == 0 or len(value) > _MAX_STRING_LENGTH:
        return False
    if _EXACT_PIN.fullmatch(value) is None:
        return False
    parts = re.split(r"[._-]", value)
    return all(part.lower() not in _RESERVED_PIN_PARTS for part in parts)


def _governed_identity(request: JudgmentRequest):
    """Идентичность из каталога. Поле запроса каталог не заменяет."""
    if not isinstance(request.provider, str):
        return None
    try:
        return get_provider_identity(request.provider)
    except UnknownProviderIdentityError:
        return None


def _provider_boundary_error(request: JudgmentRequest) -> JudgmentErrorCategory | None:
    """Чужая или несовпавшая граница — invalid_request, не локальный допуск."""
    identity = _governed_identity(request)
    if identity is None or request.network_boundary is not identity.network_boundary:
        return JudgmentErrorCategory.INVALID_REQUEST
    return None


def _decision_pack_known(
    request: JudgmentRequest,
    resolver: Callable[[str, str], bool] | None,
    now: float | None = None,
) -> bool:
    """Нет резолвера, ошибка резолвера, превышение срока или не-True — пакет неизвестен."""
    if not callable(resolver):
        return False
    if now is not None:
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
    else:
        try:
            known = resolver(request.decision_pack_id, request.decision_pack_version)
        except Exception:
            return False
    return known is True


def _identity_text_ok(*values: object) -> bool:
    """Точный тип str и точный литерал. Сравнение с враждебным __eq__ сюда не доходит."""
    return all(type(item) is str and _exact_pin(item) for item in values)


def _privacy_allows(request: JudgmentRequest) -> bool:
    """Граница берётся из каталога или фиксирована для mock_judgment."""
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


def _deadline_open(request: JudgmentRequest, clock: Callable[[], float]) -> bool:
    return _open_at(request, _safe_now(clock))


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
    elapsed = now - started
    if elapsed < 0:
        return 0
    return int(elapsed * 1000)


_MAX_CONCURRENT_WORKERS = 16
_WORKER_SEMAPHORE = threading.Semaphore(_MAX_CONCURRENT_WORKERS)


def _run_with_daemon_timeout(func: Callable, *args: object, timeout_seconds: float) -> object:
    """Выполнить функцию в фоновом daemon-потоке с ограниченным пулом воркеров и таймаутом."""
    import threading
    if timeout_seconds <= 0:
        raise FutureTimeoutError()

    acquired = _WORKER_SEMAPHORE.acquire(blocking=True, timeout=timeout_seconds)
    if not acquired:
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
    return future.result(timeout=timeout_seconds)


def _judge_within_deadline(active: JudgmentProvider, request: JudgmentRequest, now: float) -> object:
    """Ждём judge только оставшийся срок. Опоздавший результат не читаем."""
    try:
        remaining = float(request.deadline_monotonic) - now
    except OverflowError:
        remaining = 0.0
    if remaining <= 0:
        raise FutureTimeoutError()
    # Один рабочий поток. Отмена не убивает уже начатый judge, но ожидание кончается.
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
        choice=response.choice,
        score=response.score,
        noul=response.noul,
        error=response.error,
    )


def _checked_provider_result(request: JudgmentRequest, raw: object, latency_ms: int) -> JudgmentResponse:
    if not isinstance(raw, JudgmentResponse):
        return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
    # Идентичность раньше вариантов и раньше любого равенства.
    if not _response_identity_ok(raw):
        return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
    if not _identity_matches(request, raw):
        return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
    # Сначала тип. Потом поля. Иначе битый choice даёт AttributeError наружу.
    if raw.choice is not None and not isinstance(raw.choice, Choice):
        return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
    if raw.score is not None and not isinstance(raw.score, Score):
        return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
    if raw.noul is not None and not isinstance(raw.noul, Noul):
        return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
    if raw.error is not None and not isinstance(raw.error, JudgmentErrorCategory):
        return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
    variants = (raw.choice is not None, raw.noul is not None, raw.error is not None)
    if sum(1 for item in variants if item) != 1:
        return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
    if raw.error is not None:
        if not isinstance(raw.error, JudgmentErrorCategory):
            return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
        if raw.score is not None or raw.choice is not None or raw.noul is not None:
            return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
        return _error_response(request, raw.error, latency_ms)
    if raw.noul is not None:
        if request.noul_allowed is not True:
            return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
        if not isinstance(raw.noul.reason_code, NoulReason) or raw.choice is not None or raw.score is not None:
            return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
        return _success_response(request, None, None, raw.noul, latency_ms)
    choice = raw.choice
    if choice is None or type(choice.value) is not str or not _exact_pin(choice.value) or choice.value not in request.allowed_choices:
        return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
    score_error = _score_error(request, raw.score)
    if score_error is not None:
        return _error_response(request, score_error, latency_ms)
    return _success_response(request, choice, raw.score, None, latency_ms)


def _score_error(request: JudgmentRequest, score: Score | None) -> JudgmentErrorCategory | None:
    if request.score_scale is None:
        if score is not None:
            return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
        return None
    if score is None or not isinstance(score, Score) or type(score.score_id) is not str or not _exact_pin(score.score_id):
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    if score.score_id != request.score_scale.score_id:
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    if not _finite_number(score.value):
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    if score.value < request.score_scale.minimum or score.value > request.score_scale.maximum:
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    return None


def _response_identity_ok(raw: JudgmentResponse) -> bool:
    """Тип и грамматика до равенства. И у ответа, и у телеметрии."""
    if not _identity_text_ok(
        raw.provider,
        raw.model,
        raw.model_version,
        raw.decision_pack_id,
        raw.decision_pack_version,
    ):
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
    # К этому месту обе стороны уже строки. Враждебный __eq__ не вызывается.
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


def _success_response(
    request: JudgmentRequest,
    choice: Choice | None,
    score: Score | None,
    noul: Noul | None,
    latency_ms: int,
) -> JudgmentResponse:
    outcome = JudgmentOutcome.NOUL if noul is not None else JudgmentOutcome.CHOICE
    telemetry = _telemetry(request, outcome, None, latency_ms)
    return JudgmentResponse(
        provider=request.provider,
        model=request.model,
        model_version=request.model_version,
        decision_pack_id=request.decision_pack_id,
        decision_pack_version=request.decision_pack_version,
        telemetry=telemetry,
        choice=choice,
        score=score,
        noul=noul,
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
        choice=None,
        score=None,
        noul=None,
        error=category,
    )


def _unvalidated_error(category: JudgmentErrorCategory, latency_ms: int) -> JudgmentResponse:
    """Ответ на непроверенный ввод. Поля вызывающего сюда не копируются."""
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
        error=category,
    )


def _telemetry(
    request: JudgmentRequest,
    outcome: JudgmentOutcome,
    error_category: JudgmentErrorCategory | None,
    latency_ms: int,
) -> JudgmentTelemetry:
    # retry_count остаётся 0: J1 не делает повтор. Будущий повтор ест тот же срок.
    return JudgmentTelemetry(
        outcome=outcome,
        error_category=error_category,
        latency_ms=latency_ms,
        retry_count=0,
        provider=request.provider,
        model=request.model,
        model_version=request.model_version,
        decision_pack_id=request.decision_pack_id,
        decision_pack_version=request.decision_pack_version,
    )


def _request_document(request: JudgmentRequest) -> dict:
    scale = None
    if request.score_scale is not None:
        scale = {
            "maximum": request.score_scale.maximum,
            "minimum": request.score_scale.minimum,
            "score_id": request.score_scale.score_id,
        }
    return {
        "allowed_choices": list(request.allowed_choices),
        "criterion_id": request.criterion_id,
        "data_class": request.data_class.value,
        "deadline_monotonic": request.deadline_monotonic,
        "decision_pack_id": request.decision_pack_id,
        "decision_pack_version": request.decision_pack_version,
        "hosted_boundary": request.hosted_boundary,
        "model": request.model,
        "model_version": request.model_version,
        "network_boundary": request.network_boundary.value,
        "noul_allowed": request.noul_allowed,
        "outbound_form": request.outbound_form.value,
        "payload": request.payload,
        "provider": request.provider,
        "request_egress_authorized": request.request_egress_authorized,
        "request_id": request.request_id,
        "score_scale": scale,
    }


def _response_document(response: JudgmentResponse) -> dict:
    score = None
    if response.score is not None:
        score = {"score_id": response.score.score_id, "value": response.score.value}
    return {
        "choice": None if response.choice is None else response.choice.value,
        "decision_pack_id": response.decision_pack_id,
        "decision_pack_version": response.decision_pack_version,
        "error": None if response.error is None else response.error.value,
        "model": response.model,
        "model_version": response.model_version,
        "noul": None if response.noul is None else response.noul.reason_code.value,
        "provider": response.provider,
        "score": score,
        "telemetry": {
            "decision_pack_id": response.telemetry.decision_pack_id,
            "decision_pack_version": response.telemetry.decision_pack_version,
            "error_category": None if response.telemetry.error_category is None else response.telemetry.error_category.value,
            "latency_ms": response.telemetry.latency_ms,
            "model": response.telemetry.model,
            "model_version": response.telemetry.model_version,
            "outcome": response.telemetry.outcome.value,
            "error_category": None if response.telemetry.error_category is None else response.telemetry.error_category.value,
            "provider": response.telemetry.provider,
            "retry_count": response.telemetry.retry_count,
        },
    }


def _safe_now(clock: Callable[[], float]) -> float | None:
    """Конечное монотонное время. Невалидные часы — это None, не ноль."""
    try:
        value = clock()
    except Exception:
        # Часы — внешний callback. Любой обычный сбой значит «время неизвестно».
        return None
    if not _finite_number(value):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except OverflowError:
        return None


def _safe_latency(started: float | None, clock: Callable[[], float]) -> int:
    now = _safe_now(clock)
    if now is None or started is None:
        return 0
    elapsed = now - started
    if elapsed < 0:
        return 0
    return int(elapsed * 1000)
