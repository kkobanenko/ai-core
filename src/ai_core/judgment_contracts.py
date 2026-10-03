"""Вызываемый контракт J1. Это улика, не разрешение.

Провайдер здесь не выбирается и не ходит в сеть.
Живой каталог JUDGMENT этот модуль не пополняет.
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from ai_core.privacy import DataClass, OutboundForm, is_egress_eligible
from ai_core.provider_catalog import NetworkBoundary

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
    provider: JudgmentProvider | None = None,
    *,
    provider_factory: Callable[[], JudgmentProvider] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> JudgmentResponse:
    """Проверить запрос, затем границу, затем срок, затем провайдера.

    Повтор и запасной провайдер в J1 не выполняются.
    Общий монотонный срок остаётся одним на будущий повтор.
    """
    started = _safe_now(clock)
    if not isinstance(request, JudgmentRequest):
        return _unvalidated_error(JudgmentErrorCategory.INVALID_REQUEST, _safe_latency(started, clock))
    try:
        invalid = _request_error(request)
    except (AttributeError, TypeError, OverflowError):
        return _unvalidated_error(JudgmentErrorCategory.INVALID_REQUEST, _safe_latency(started, clock))
    if invalid is not None:
        return _unvalidated_error(invalid, _safe_latency(started, clock))
    if not _privacy_allows(request):
        return _error_response(request, JudgmentErrorCategory.PRIVACY_EGRESS_DENIED, _safe_latency(started, clock))
    if not _deadline_open(request, clock):
        return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, _safe_latency(started, clock))
    try:
        active = provider if provider is not None else None
        if active is None:
            if provider_factory is None:
                return _error_response(request, JudgmentErrorCategory.INTERNAL_ERROR, _safe_latency(started, clock))
            active = provider_factory()
            # Фабрика могла съесть срок. judge после этого не стартует.
            if not _deadline_open(request, clock):
                return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, _safe_latency(started, clock))
        raw = active.judge(request)
    except Exception:
        # Текст исключения наружу не отдаём: в нём может быть нагрузка.
        return _error_response(request, JudgmentErrorCategory.INTERNAL_ERROR, _safe_latency(started, clock))
    latency = _safe_latency(started, clock)
    try:
        checked = _checked_provider_result(request, raw, latency)
    except (AttributeError, TypeError):
        checked = _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency)
    # Последняя проверка срока. После неё результат только отдаётся.
    if not _deadline_open(request, clock):
        return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, latency)
    return checked


def request_to_json(request: JudgmentRequest) -> str:
    """Стабильный JSON запроса. Невалидный запрос не сериализуется."""
    if not isinstance(request, JudgmentRequest) or _request_error(request) is not None:
        raise ValueError("request is not a valid J1 contract")
    return json.dumps(_request_document(request), ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def request_from_json(text: str) -> JudgmentRequest:
    """Собрать запрос из JSON. Неверный тип поля не приводится к строке."""
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError("request JSON must be an object")
    if set(loaded) != _REQUEST_JSON_KEYS:
        raise ValueError("request JSON fields are not the closed set")
    choices = loaded.get("allowed_choices")
    if not isinstance(choices, list) or any(not isinstance(item, str) for item in choices):
        raise ValueError("allowed_choices must be a list of strings")
    return JudgmentRequest(
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


def response_to_json(response: JudgmentResponse) -> str:
    """Стабильный JSON ответа. Невалидная структура не сериализуется."""
    if _structural_problem(response) is not None:
        raise ValueError("response is not a valid J1 contract")
    return json.dumps(_response_document(response), ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def response_from_json(text: str) -> JudgmentResponse:
    """Собрать ответ из JSON. Неверный тип поля не приводится к строке."""
    loaded = json.loads(text)
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
    if response.choice is None or response.choice.value not in request.allowed_choices:
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    return _score_error(request, response.score)


def _structural_problem(response: JudgmentResponse) -> str | None:
    """Инварианты ответа без знания запроса."""
    if not isinstance(response, JudgmentResponse):
        return "response type"
    if not all(_exact_pin(item) for item in (
        response.provider,
        response.model,
        response.model_version,
        response.decision_pack_id,
        response.decision_pack_version,
    )):
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
    if response.choice is not None and not _exact_pin(response.choice.value):
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
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _json_text(value: object, name: str) -> str:
    if not isinstance(value, str):
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
    if any(not isinstance(item, str) for item in names):
        return JudgmentErrorCategory.INVALID_REQUEST
    if any(not _exact_pin(item) for item in names):
        return JudgmentErrorCategory.INVALID_REQUEST
    choices = request.allowed_choices
    if not isinstance(choices, tuple):
        return JudgmentErrorCategory.INVALID_REQUEST
    if any(not isinstance(item, str) for item in choices):
        return JudgmentErrorCategory.INVALID_REQUEST
    if len(choices) == 0 or len(set(choices)) != len(choices):
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
    # Флаг hosted не может объявить внешнюю границу локальной.
    if request.hosted_boundary is True and request.network_boundary is not NetworkBoundary.EXTERNAL:
        return JudgmentErrorCategory.INVALID_REQUEST
    return None


def _scale_ok(scale: object) -> bool:
    if not isinstance(scale, ScoreScale):
        return False
    if not isinstance(scale.score_id, str) or not _exact_pin(scale.score_id):
        return False
    if not _finite_number(scale.minimum) or not _finite_number(scale.maximum):
        return False
    return scale.minimum < scale.maximum


def _finite_number(value: object) -> bool:
    """Конечное число. Огромный int не превращается в OverflowError."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if isinstance(value, int) and value.bit_length() > 1023:
        return False
    try:
        number = float(value)
    except OverflowError:
        return False
    return math.isfinite(number)


def _nonnegative_int(value: object) -> bool:
    """Сначала тип. Потом знак. bool не является счётчиком."""
    if isinstance(value, bool) or not isinstance(value, int):
        return False
    return value >= 0


def _exact_pin(value: object) -> bool:
    """Точный литерал на всю строку. Селектор не проходит."""
    if not isinstance(value, str):
        return False
    if _EXACT_PIN.fullmatch(value) is None:
        return False
    parts = re.split(r"[._-]", value)
    return all(part.lower() not in _RESERVED_PIN_PARTS for part in parts)


def _privacy_allows(request: JudgmentRequest) -> bool:
    """Неизвестная граница не даёт права. Флаг hosted_boundary их не расширяет."""
    if request.network_boundary is NetworkBoundary.UNKNOWN_BOUNDARY:
        return False
    eligible = is_egress_eligible(
        data_class=request.data_class,
        outbound_form=request.outbound_form,
        network_boundary=request.network_boundary,
        request_egress_authorized=request.request_egress_authorized,
    )
    if eligible is not True:
        return False
    if request.network_boundary is NetworkBoundary.EXTERNAL:
        if request.request_egress_authorized is not True:
            return False
        return request.data_class in HOSTED_DATA_CLASSES
    return True


def _deadline_open(request: JudgmentRequest, clock: Callable[[], float]) -> bool:
    if not _finite_number(request.deadline_monotonic):
        return False
    try:
        deadline = float(request.deadline_monotonic)
    except OverflowError:
        return False
    return _safe_now(clock) < deadline


def _checked_provider_result(request: JudgmentRequest, raw: object, latency_ms: int) -> JudgmentResponse:
    if not isinstance(raw, JudgmentResponse):
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
    if not _identity_matches(request, raw):
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
    if choice is None or not isinstance(choice.value, str) or choice.value not in request.allowed_choices:
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
    if score is None or not isinstance(score, Score) or not isinstance(score.score_id, str):
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    if score.score_id != request.score_scale.score_id:
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    if isinstance(score.value, bool) or not isinstance(score.value, (int, float)) or not math.isfinite(score.value):
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    if score.value < request.score_scale.minimum or score.value > request.score_scale.maximum:
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    return None


def _identity_matches(request: JudgmentRequest, raw: JudgmentResponse) -> bool:
    return (
        raw.provider == request.provider
        and raw.model == request.model
        and raw.model_version == request.model_version
        and raw.decision_pack_id == request.decision_pack_id
        and raw.decision_pack_version == request.decision_pack_version
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


def _safe_now(clock: Callable[[], float]) -> float:
    try:
        value = float(clock())
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value):
        return 0.0
    return value


def _safe_latency(started: float, clock: Callable[[], float]) -> int:
    elapsed = _safe_now(clock) - started
    if elapsed < 0:
        return 0
    return int(elapsed * 1000)
