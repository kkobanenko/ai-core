"""Вызываемый контракт J1. Это улика, не разрешение.

Провайдер здесь не выбирается и не ходит в сеть.
Живой каталог JUDGMENT этот модуль не пополняет.
"""

from __future__ import annotations

import json
import math
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
# Для внешней границы суждения годны только эти классы.
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

    reason_code: str


@dataclass(frozen=True)
class JudgmentTelemetry:
    """Только метаданные. Полезная нагрузка и секреты сюда не входят."""

    outcome: str
    error_category: str
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
    started = _now(clock)
    invalid = _request_error(request)
    if invalid is not None:
        return _error_response(request, invalid, _latency(started, clock))
    if not _privacy_allows(request):
        return _error_response(request, JudgmentErrorCategory.PRIVACY_EGRESS_DENIED, _latency(started, clock))
    if not _deadline_open(request, clock):
        return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, _latency(started, clock))
    try:
        active = provider if provider is not None else None
        if active is None:
            if provider_factory is None:
                return _error_response(request, JudgmentErrorCategory.INTERNAL_ERROR, _latency(started, clock))
            active = provider_factory()
        raw = active.judge(request)
    except Exception:
        # Текст исключения наружу не отдаём: в нём может быть нагрузка.
        return _error_response(request, JudgmentErrorCategory.INTERNAL_ERROR, _latency(started, clock))
    return _checked_provider_result(request, raw, _latency(started, clock))


def request_to_json(request: JudgmentRequest) -> str:
    """Стабильный JSON запроса. Провайдер и часы не сериализуются."""
    return json.dumps(_request_document(request), ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def request_from_json(text: str) -> JudgmentRequest:
    """Собрать запрос из JSON. Неизвестный ключ отвергается."""
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError("request JSON must be an object")
    scale = loaded.get("score_scale")
    parsed_scale = None
    if scale is not None:
        parsed_scale = ScoreScale(
            score_id=str(scale["score_id"]),
            minimum=float(scale["minimum"]),
            maximum=float(scale["maximum"]),
        )
    return JudgmentRequest(
        request_id=str(loaded["request_id"]),
        decision_pack_id=str(loaded["decision_pack_id"]),
        decision_pack_version=str(loaded["decision_pack_version"]),
        criterion_id=str(loaded["criterion_id"]),
        allowed_choices=tuple(str(item) for item in loaded["allowed_choices"]),
        noul_allowed=loaded["noul_allowed"] is True,
        data_class=DataClass(str(loaded["data_class"])),
        outbound_form=OutboundForm(str(loaded["outbound_form"])),
        network_boundary=NetworkBoundary(str(loaded["network_boundary"])),
        request_egress_authorized=loaded["request_egress_authorized"] is True,
        hosted_boundary=loaded["hosted_boundary"] is True,
        deadline_monotonic=float(loaded["deadline_monotonic"]),
        provider=str(loaded["provider"]),
        model=str(loaded["model"]),
        model_version=str(loaded["model_version"]),
        payload=loaded.get("payload"),
        score_scale=parsed_scale,
    )


def response_to_json(response: JudgmentResponse) -> str:
    """Стабильный JSON ответа. Сырой текст провайдера сюда не входит."""
    return json.dumps(_response_document(response), ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def response_from_json(text: str) -> JudgmentResponse:
    """Собрать ответ из JSON."""
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError("response JSON must be an object")
    telemetry = JudgmentTelemetry(**loaded["telemetry"])
    choice = None if loaded.get("choice") is None else Choice(str(loaded["choice"]))
    score = None
    if loaded.get("score") is not None:
        score = Score(score_id=str(loaded["score"]["score_id"]), value=float(loaded["score"]["value"]))
    noul = None if loaded.get("noul") is None else Noul(str(loaded["noul"]))
    error = None if loaded.get("error") is None else JudgmentErrorCategory(str(loaded["error"]))
    return JudgmentResponse(
        provider=str(loaded["provider"]),
        model=str(loaded["model"]),
        model_version=str(loaded["model_version"]),
        decision_pack_id=str(loaded["decision_pack_id"]),
        decision_pack_version=str(loaded["decision_pack_version"]),
        telemetry=telemetry,
        choice=choice,
        score=score,
        noul=noul,
        error=error,
    )


def grants_authority(response: JudgmentResponse) -> bool:
    """Контракт не выдаёт права. Истина здесь означает нарушение инварианта."""
    document = _response_document(response)
    return any(name in document for name in FORBIDDEN_AUTHORITY)


def _request_error(request: JudgmentRequest) -> JudgmentErrorCategory | None:
    names = (
        request.request_id,
        request.decision_pack_id,
        request.decision_pack_version,
        request.criterion_id,
        request.provider,
        request.model,
        request.model_version,
    )
    if any(not isinstance(item, str) or item.strip() == "" for item in names):
        return JudgmentErrorCategory.INVALID_REQUEST
    if not _exact_pin(request.provider) or not _exact_pin(request.model) or not _exact_pin(request.model_version):
        return JudgmentErrorCategory.INVALID_REQUEST
    if not _exact_pin(request.decision_pack_id) or not _exact_pin(request.decision_pack_version):
        return JudgmentErrorCategory.INVALID_REQUEST
    if not isinstance(request.criterion_id, str) or not _exact_pin(request.criterion_id):
        return JudgmentErrorCategory.INVALID_REQUEST
    if len(request.allowed_choices) == 0:
        return JudgmentErrorCategory.INVALID_REQUEST
    if len(set(request.allowed_choices)) != len(request.allowed_choices):
        return JudgmentErrorCategory.INVALID_REQUEST
    if any(not isinstance(item, str) or item.strip() == "" for item in request.allowed_choices):
        return JudgmentErrorCategory.INVALID_REQUEST
    if not isinstance(request.data_class, DataClass) or not isinstance(request.outbound_form, OutboundForm):
        return JudgmentErrorCategory.INVALID_REQUEST
    if not isinstance(request.network_boundary, NetworkBoundary):
        return JudgmentErrorCategory.INVALID_REQUEST
    if not isinstance(request.deadline_monotonic, (int, float)) or isinstance(request.deadline_monotonic, bool):
        return JudgmentErrorCategory.INVALID_REQUEST
    if not math.isfinite(float(request.deadline_monotonic)):
        return JudgmentErrorCategory.INVALID_REQUEST
    if request.score_scale is not None and not _scale_ok(request.score_scale):
        return JudgmentErrorCategory.INVALID_REQUEST
    return None


def _scale_ok(scale: ScoreScale) -> bool:
    if scale.score_id.strip() == "" or not _exact_pin(scale.score_id):
        return False
    if not math.isfinite(scale.minimum) or not math.isfinite(scale.maximum):
        return False
    return scale.minimum < scale.maximum


def _exact_pin(value: str) -> bool:
    """Точный идентификатор. latest и суффикс -latest запрещены."""
    text = value.strip().lower()
    if text == "" or text == "latest":
        return False
    if text.endswith("-latest") or text.endswith("_latest"):
        return False
    return True


def _privacy_allows(request: JudgmentRequest) -> bool:
    """Сначала общий egress, затем более узкое правило внешней границы."""
    eligible = is_egress_eligible(
        data_class=request.data_class,
        outbound_form=request.outbound_form,
        network_boundary=request.network_boundary,
        request_egress_authorized=request.request_egress_authorized,
    )
    if eligible is not True:
        return False
    if request.hosted_boundary is not True:
        return True
    if request.network_boundary is not NetworkBoundary.EXTERNAL:
        return False
    if request.request_egress_authorized is not True:
        return False
    return request.data_class in HOSTED_DATA_CLASSES


def _deadline_open(request: JudgmentRequest, clock: Callable[[], float]) -> bool:
    return _now(clock) < float(request.deadline_monotonic)


def _checked_provider_result(request: JudgmentRequest, raw: object, latency_ms: int) -> JudgmentResponse:
    if not isinstance(raw, JudgmentResponse):
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
        if raw.noul.reason_code.strip() == "" or raw.choice is not None or raw.score is not None:
            return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)
        return _success_response(request, None, None, raw.noul, latency_ms)
    choice = raw.choice
    if choice is None or choice.value not in request.allowed_choices:
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
    if score is None or score.score_id != request.score_scale.score_id:
        return JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE
    if not math.isfinite(score.value):
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
    outcome = "noul" if noul is not None else "choice"
    telemetry = _telemetry(request, outcome, "", latency_ms)
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
    telemetry = _telemetry(request, "error", category.value, latency_ms)
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


def _telemetry(request: JudgmentRequest, outcome: str, error_category: str, latency_ms: int) -> JudgmentTelemetry:
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
        "noul": None if response.noul is None else response.noul.reason_code,
        "provider": response.provider,
        "score": score,
        "telemetry": {
            "decision_pack_id": response.telemetry.decision_pack_id,
            "decision_pack_version": response.telemetry.decision_pack_version,
            "error_category": response.telemetry.error_category,
            "latency_ms": response.telemetry.latency_ms,
            "model": response.telemetry.model,
            "model_version": response.telemetry.model_version,
            "outcome": response.telemetry.outcome,
            "provider": response.telemetry.provider,
            "retry_count": response.telemetry.retry_count,
        },
    }


def _now(clock: Callable[[], float]) -> float:
    value = float(clock())
    if not math.isfinite(value):
        raise ValueError("clock is not finite")
    return value


def _latency(started: float, clock: Callable[[], float]) -> int:
    try:
        elapsed = _now(clock) - started
    except ValueError:
        return 0
    if elapsed < 0:
        return 0
    return int(elapsed * 1000)
