"""Метаданные telemetry для judgment без семантического payload."""

from __future__ import annotations

from typing import Any, Mapping

from ai_core.judgment_contracts import JudgmentResponse
from ai_core.judgment_errors import JudgmentError, JudgmentErrorCategory

# Запрещённые ключи в публичных событиях telemetry.
_FORBIDDEN_TELEMETRY_KEYS = frozenset(
    {
        "shared_state",
        "questions",
        "question_text",
        "instructions",
        "prompt",
        "raw_provider_response",
        "provider_raw",
        "selected",
        "expected_score",
        "probability_true",
        "probabilities",
        "confidence",
        "answer",
        "credentials",
        "secret",
        "api_key",
    }
)


def build_success_telemetry_event(
    response: JudgmentResponse,
    *,
    outcome: str = "success",
) -> Mapping[str, Any]:
    """Собрать разрешённые метаданные успешного вызова."""

    event = {
        "outcome": outcome,
        "error_category": None,
        "latency_ms": response.latency_ms,
        "retry_count": response.retry_count,
        "provider_id": response.provider_pin.provider_id,
        "model": response.provider_pin.model,
        "model_version": response.provider_pin.model_version,
        "decision_pack_id": response.decision_pack.decision_pack_id,
        "decision_pack_version": response.decision_pack.decision_pack_version,
        "request_id": response.request_id,
    }
    _assert_telemetry_safe(event)
    return event


def build_error_telemetry_event(
    error: JudgmentError,
    *,
    request_id: str,
    decision_pack_id: str,
    decision_pack_version: str,
    provider_id: str,
    model: str,
    model_version: str,
    latency_ms: float,
    retry_count: int,
) -> Mapping[str, Any]:
    """Собрать метаданные для ошибки без утечки provider payload."""

    event = {
        "outcome": "error",
        "error_category": error.category.value,
        "latency_ms": latency_ms,
        "retry_count": retry_count,
        "provider_id": provider_id,
        "model": model,
        "model_version": model_version,
        "decision_pack_id": decision_pack_id,
        "decision_pack_version": decision_pack_version,
        "request_id": request_id,
        "message": error.message,
    }
    _assert_telemetry_safe(event)
    return event


def _assert_telemetry_safe(event: Mapping[str, Any]) -> None:
    for key in event:
        lowered = key.lower()
        if lowered in _FORBIDDEN_TELEMETRY_KEYS:
            raise ValueError(f"forbidden telemetry key: {key}")
        if "password" in lowered or "token" in lowered:
            raise ValueError(f"forbidden telemetry key pattern: {key}")


def is_retryable_error(category: JudgmentErrorCategory) -> bool:
    """Категории, для которых допустим bounded retry внутри общего deadline."""

    return category in {
        JudgmentErrorCategory.RATE_LIMITED,
        JudgmentErrorCategory.PROVIDER_UNAVAILABLE,
        JudgmentErrorCategory.TRANSPORT_FAILED,
    }


__all__ = [
    "build_error_telemetry_event",
    "build_success_telemetry_event",
    "is_retryable_error",
]
