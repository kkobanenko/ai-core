"""Dependency-light error metadata for bounded AI routing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AiErrorKind(str, Enum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    BAD_REQUEST = "bad_request"
    NOT_FOUND = "not_found"
    SERVER = "server"
    TRANSPORT = "transport"
    DEADLINE_EXHAUSTED = "deadline_exhausted"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ErrorDescriptor:
    """Normalized provider-error metadata without payload or credentials."""

    kind: AiErrorKind
    status_code: int | None
    retryable_same_provider: bool
    fallback_eligible: bool
    terminal: bool


class AiCoreRoutingError(RuntimeError):
    """Base class for bounded-routing planning errors."""


class NoEligibleProviderError(AiCoreRoutingError):
    """No candidate survived the explicit planning gates."""


class RequestDeadlineExceededError(AiCoreRoutingError, TimeoutError):
    """Shared request deadline leaves no safe attempt budget."""


def _status_code(error: BaseException) -> int | None:
    for attr in ("status_code", "code", "status"):
        status = getattr(error, attr, None)
        if isinstance(status, int):
            return status

    response = getattr(error, "response", None)
    if response is not None:
        for attr in ("status_code", "status", "code"):
            response_status = getattr(response, attr, None)
            if isinstance(response_status, int):
                return response_status

    return None



def classify_provider_error(error: BaseException) -> ErrorDescriptor:
    """Classify an error without importing any provider SDK."""

    if isinstance(error, TimeoutError):
        return ErrorDescriptor(
            AiErrorKind.TIMEOUT,
            None,
            True,
            True,
            False,
        )

    status = _status_code(error)

    if status == 429:
        return ErrorDescriptor(
            AiErrorKind.RATE_LIMIT,
            status,
            True,
            True,
            False,
        )

    if status in (401, 403):
        return ErrorDescriptor(
            AiErrorKind.AUTH,
            status,
            False,
            False,
            True,
        )

    if status == 400:
        return ErrorDescriptor(
            AiErrorKind.BAD_REQUEST,
            status,
            False,
            False,
            True,
        )

    if status == 404:
        return ErrorDescriptor(
            AiErrorKind.NOT_FOUND,
            status,
            False,
            False,
            True,
        )

    if status is not None and 500 <= status <= 599:
        return ErrorDescriptor(
            AiErrorKind.SERVER,
            status,
            False,
            True,
            False,
        )

    if status is not None:
        return ErrorDescriptor(
            AiErrorKind.UNKNOWN,
            status,
            False,
            False,
            True,
        )

    class_name = error.__class__.__name__

    if any(
        marker in class_name
        for marker in ("Timeout", "APITimeout")
    ):
        return ErrorDescriptor(
            AiErrorKind.TIMEOUT,
            None,
            True,
            True,
            False,
        )

    if "RateLimit" in class_name:
        return ErrorDescriptor(
            AiErrorKind.RATE_LIMIT,
            None,
            True,
            True,
            False,
        )

    if any(
        marker in class_name
        for marker in (
            "Connect",
            "Connection",
            "Transport",
            "Network",
            "Protocol",
        )
    ):
        return ErrorDescriptor(
            AiErrorKind.TRANSPORT,
            None,
            False,
            True,
            False,
        )

    return ErrorDescriptor(
        AiErrorKind.UNKNOWN,
        None,
        False,
        False,
        True,
    )


__all__ = [
    "AiCoreRoutingError",
    "AiErrorKind",
    "ErrorDescriptor",
    "NoEligibleProviderError",
    "RequestDeadlineExceededError",
    "classify_provider_error",
]
