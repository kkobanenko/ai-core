"""Нормализованные ошибки семантического judgment (провайдер-нейтральные)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class JudgmentErrorCategory(str, Enum):
    """Канонические категории ошибок judgment."""

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
class JudgmentError:
    """Публичная ошибка без утечки сырых ответов провайдера."""

    category: JudgmentErrorCategory
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.category, JudgmentErrorCategory):
            raise TypeError("category must be JudgmentErrorCategory")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("message must be a non-empty safe string")


def judgment_error(
    category: JudgmentErrorCategory,
    message: str,
) -> JudgmentError:
    """Собрать типизированную ошибку judgment."""

    return JudgmentError(category=category, message=message.strip())


__all__ = [
    "JudgmentError",
    "JudgmentErrorCategory",
    "judgment_error",
]
