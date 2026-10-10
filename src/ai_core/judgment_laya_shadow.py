"""J2 shadow Laya adapter (opt-in, disabled by default).

Не входит в provider catalog и не меняет invoke_judgment (J1).
Нет зависимости от torch/laya: только HTTP к локальному laya-serve.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Protocol

from ai_core.judgment_contracts import (
    BinaryAnswer,
    BinaryQuestion,
    JudgmentErrorCategory,
    JudgmentOutcome,
    JudgmentRequest,
    JudgmentResponse,
    JudgmentTelemetry,
    validate_response_for_request,
)
from ai_core.privacy import DataClass, OutboundForm, is_egress_eligible
from ai_core.provider_catalog import NetworkBoundary

# Пин одного checkpoint (multilingual 322M).
LAYA_SHADOW_PROVIDER_ID = "laya_multilingual_shadow"
LAYA_SHADOW_MODEL_ID = "laya-multilingual"
LAYA_SHADOW_MODEL_VERSION = "convaiinnovations-laya-multilingual-main"

_ENV_ENABLE = "AI_CORE_LAYA_J2_SHADOW_ADAPTER_ENABLED"
_ENV_ENDPOINT = "AI_CORE_LAYA_SHADOW_ENDPOINT"
_DEFAULT_ENDPOINT = "http://127.0.0.1:8080/v1/judge"


class HttpPostFn(Protocol):
    def __call__(self, url: str, body: bytes, headers: dict[str, str], timeout: float) -> tuple[int, bytes]: ...


def laya_shadow_adapter_enabled() -> bool:
    """Явное включение адаптера. По умолчанию выключено."""
    return os.environ.get(_ENV_ENABLE, "").strip().lower() in ("1", "true", "yes")


def laya_shadow_endpoint() -> str:
    return os.environ.get(_ENV_ENDPOINT, _DEFAULT_ENDPOINT).strip() or _DEFAULT_ENDPOINT


def _telemetry(
    request: JudgmentRequest,
    outcome: JudgmentOutcome,
    error: JudgmentErrorCategory | None,
    latency_ms: int,
) -> JudgmentTelemetry:
    return JudgmentTelemetry(
        outcome=outcome,
        error_category=error,
        latency_ms=latency_ms,
        retry_count=0,
        provider=request.provider,
        model=request.model,
        model_version=request.model_version,
        decision_pack_id=request.decision_pack_id,
        decision_pack_version=request.decision_pack_version,
    )


def _error_response(
    request: JudgmentRequest,
    category: JudgmentErrorCategory,
    latency_ms: int,
) -> JudgmentResponse:
    return JudgmentResponse(
        provider=request.provider,
        model=request.model,
        model_version=request.model_version,
        decision_pack_id=request.decision_pack_id,
        decision_pack_version=request.decision_pack_version,
        telemetry=_telemetry(request, JudgmentOutcome.ERROR, category, latency_ms),
        answers=None,
        error=category,
    )


def _extract_text(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    text = payload.get("text")
    if type(text) is not str or not text.strip():
        return None
    return text.strip()[:600]


def _questions_to_laya(request: JudgmentRequest) -> list[dict[str, str | None]]:
    items: list[dict[str, str | None]] = []
    for name, question in request.questions:
        if not isinstance(name, str) or not isinstance(question, BinaryQuestion):
            continue
        items.append(
            {
                "name": name,
                "instructions": question.instructions,
                "true_criterion": question.true_criterion,
                "false_criterion": question.false_criterion,
            }
        )
    return items


def _default_http_post(url: str, body: bytes, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read()
    except urllib.error.HTTPError as err:
        return int(err.code), err.read()
    except urllib.error.URLError:
        raise


def invoke_laya_shadow_judgment(
    request: JudgmentRequest,
    *,
    clock: Callable[[], float] = time.monotonic,
    decision_pack_known: Callable[[str, str], bool] | None = None,
    http_post: HttpPostFn | None = None,
) -> JudgmentResponse:
    """Shadow-only Laya inference через HTTP. Не заменяет invoke_judgment."""
    started = clock()
    latency_ms = 0

    if not laya_shadow_adapter_enabled():
        return JudgmentResponse(
            provider=getattr(request, "provider", "unvalidated"),
            model=getattr(request, "model", "unvalidated"),
            model_version=getattr(request, "model_version", "unvalidated"),
            decision_pack_id=getattr(request, "decision_pack_id", "unvalidated"),
            decision_pack_version=getattr(request, "decision_pack_version", "unvalidated"),
            telemetry=JudgmentTelemetry(
                outcome=JudgmentOutcome.ERROR,
                error_category=JudgmentErrorCategory.INVALID_REQUEST,
                latency_ms=0,
                retry_count=0,
                provider=str(getattr(request, "provider", "unvalidated")),
                model=str(getattr(request, "model", "unvalidated")),
                model_version=str(getattr(request, "model_version", "unvalidated")),
                decision_pack_id=str(getattr(request, "decision_pack_id", "unvalidated")),
                decision_pack_version=str(getattr(request, "decision_pack_version", "unvalidated")),
            ),
            answers=None,
            error=JudgmentErrorCategory.INVALID_REQUEST,
        )

    if not isinstance(request, JudgmentRequest):
        return JudgmentResponse(
            provider="unvalidated",
            model="unvalidated",
            model_version="unvalidated",
            decision_pack_id="unvalidated",
            decision_pack_version="unvalidated",
            telemetry=JudgmentTelemetry(
                outcome=JudgmentOutcome.ERROR,
                error_category=JudgmentErrorCategory.INVALID_REQUEST,
                latency_ms=0,
                retry_count=0,
                provider="unvalidated",
                model="unvalidated",
                model_version="unvalidated",
                decision_pack_id="unvalidated",
                decision_pack_version="unvalidated",
            ),
            answers=None,
            error=JudgmentErrorCategory.INVALID_REQUEST,
        )

    if request.provider != LAYA_SHADOW_PROVIDER_ID:
        return _error_response(request, JudgmentErrorCategory.INVALID_REQUEST, 0)

    if request.model != LAYA_SHADOW_MODEL_ID or request.model_version != LAYA_SHADOW_MODEL_VERSION:
        return _error_response(request, JudgmentErrorCategory.INVALID_REQUEST, 0)

    if request.network_boundary is not NetworkBoundary.LOCAL_SAME_HOST or request.hosted_boundary:
        return _error_response(request, JudgmentErrorCategory.INVALID_REQUEST, 0)

    if not is_egress_eligible(
        data_class=request.data_class,
        outbound_form=request.outbound_form,
        network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
        request_egress_authorized=request.request_egress_authorized,
    ):
        return _error_response(request, JudgmentErrorCategory.PRIVACY_EGRESS_DENIED, 0)

    if clock() >= request.deadline_monotonic:
        return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, 0)

    if not callable(decision_pack_known) or not decision_pack_known(
        request.decision_pack_id, request.decision_pack_version
    ):
        return _error_response(request, JudgmentErrorCategory.INVALID_REQUEST, 0)

    text = _extract_text(request.payload)
    if text is None:
        return _error_response(request, JudgmentErrorCategory.INVALID_REQUEST, 0)

    for _name, question in request.questions:
        if not isinstance(question, BinaryQuestion):
            return _error_response(request, JudgmentErrorCategory.INVALID_REQUEST, 0)

    laya_questions = _questions_to_laya(request)
    if len(laya_questions) != len(request.questions):
        return _error_response(request, JudgmentErrorCategory.INVALID_REQUEST, 0)

    remaining = max(0.0, float(request.deadline_monotonic) - clock())
    if remaining <= 0:
        return _error_response(request, JudgmentErrorCategory.DEADLINE_EXHAUSTED, 0)

    post = http_post or _default_http_post
    body = json.dumps(
        {
            "request_id": request.request_id,
            "model": request.model,
            "model_version": request.model_version,
            "text": text,
            "questions": laya_questions,
        },
        ensure_ascii=True,
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    auth = os.environ.get("AI_CORE_LAYA_SHADOW_BEARER_TOKEN", "").strip()
    if auth:
        headers["Authorization"] = f"Bearer {auth}"

    try:
        status, raw = post(laya_shadow_endpoint(), body, headers, remaining)
    except Exception:
        latency_ms = int((clock() - started) * 1000)
        return _error_response(request, JudgmentErrorCategory.TRANSPORT_FAILED, latency_ms)

    latency_ms = int((clock() - started) * 1000)
    if status >= 400:
        return _error_response(request, JudgmentErrorCategory.PROVIDER_UNAVAILABLE, latency_ms)

    try:
        parsed = json.loads(raw.decode("utf-8"))
        answers_raw = parsed.get("answers")
        if not isinstance(answers_raw, list):
            raise ValueError("answers missing")
        answer_pairs: list[tuple[str, BinaryAnswer]] = []
        by_name = {item.get("name"): item for item in answers_raw if isinstance(item, dict)}
        for name, _question in request.questions:
            entry = by_name.get(name)
            if not isinstance(entry, dict):
                raise ValueError("missing answer")
            prob = float(entry["probability_true"])
            answer_pairs.append((name, BinaryAnswer(prob)))
    except Exception:
        return _error_response(request, JudgmentErrorCategory.INVALID_PROVIDER_RESPONSE, latency_ms)

    response = JudgmentResponse(
        provider=request.provider,
        model=request.model,
        model_version=request.model_version,
        decision_pack_id=request.decision_pack_id,
        decision_pack_version=request.decision_pack_version,
        telemetry=_telemetry(request, JudgmentOutcome.SUCCESS, None, latency_ms),
        answers=tuple(answer_pairs),
        error=None,
    )
    invalid = validate_response_for_request(response, request)
    if invalid is not None:
        return _error_response(request, invalid, latency_ms)
    return response
