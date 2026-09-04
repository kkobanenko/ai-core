"""Ошибки media-транспорта: категории без утечки секретов."""

from __future__ import annotations

from ai_core.json_client import ProviderTransportError


def _redact_secrets(message: str) -> str:
    """Грубо вычистить похожие на ключи фрагменты из текста ошибки."""
    import re

    out = message
    # Bearer tokens / long hex-like keys
    out = re.sub(r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}", "Bearer ***", out)
    out = re.sub(r"(?i)(api[_-]?key|authorization)\s*[:=]\s*\S+", r"\1=***", out)
    out = re.sub(r"sk-[A-Za-z0-9]{8,}", "sk-***", out)
    return out


class MediaAuthError(RuntimeError):
    """Терминальная auth/config ошибка (401/403) — не fallback-eligible."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        self.status_code = status_code
        self.category = "auth_error"
        super().__init__(_redact_secrets(message))

    def __repr__(self) -> str:
        return f"MediaAuthError(category={self.category!r}, status_code={self.status_code})"


class MediaTransportError(ProviderTransportError):
    """Транспортная ошибка: timeout / connection / 429 / 5xx — fallback-eligible для consumer."""

    def __init__(
        self,
        message: str,
        *,
        category: str,
        status_code: int | None = None,
    ) -> None:
        self.category = category
        self.status_code = status_code
        # ProviderTransportError — маркер «можно пробовать другого провайдера» у consumer.
        super().__init__(_redact_secrets(message))

    def __repr__(self) -> str:
        return (
            f"MediaTransportError(category={self.category!r}, "
            f"status_code={self.status_code})"
        )


def classify_http_error(status_code: int, detail: str = "") -> Exception:
    """Смапить HTTP status в типизированную ошибку (без секретов)."""
    safe = _redact_secrets(detail or f"HTTP {status_code}")
    if status_code in (401, 403):
        return MediaAuthError(safe, status_code=status_code)
    if status_code == 429:
        return MediaTransportError(safe, category="http_429", status_code=status_code)
    if 500 <= status_code <= 599:
        return MediaTransportError(safe, category="http_5xx", status_code=status_code)
    # Прочие 4xx — терминальные input/config, не транспортный fallback.
    return ValueError(safe)
