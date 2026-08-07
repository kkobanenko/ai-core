"""Независимое хранилище health по provider_id и read-only probe для Ollama."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import httpx


class ProviderHealthStatus(str, Enum):
    """Статус здоровья одного провайдера (не путать с «все Ollama»)."""

    REACHABLE = "reachable"
    UNREACHABLE = "unreachable"
    QUOTA_LIMITED = "quota_limited"
    AUTH_FAILED = "auth_failed"
    MODEL_MISSING = "model_missing"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


# Статусы, при которых провайдер нельзя выбирать в роутере.
_UNHEALTHY = frozenset(
    {
        ProviderHealthStatus.UNREACHABLE,
        ProviderHealthStatus.QUOTA_LIMITED,
        ProviderHealthStatus.AUTH_FAILED,
        ProviderHealthStatus.MODEL_MISSING,
        ProviderHealthStatus.TIMEOUT,
    }
)


@dataclass
class ProviderHealthStore:
    """Независимый статус на каждый provider_id.

    Важно: quota_limited у ollama_cloud НЕ должен помечать vm100/gpu как down.
    """

    _status: dict[str, ProviderHealthStatus] = field(default_factory=dict)

    def set_status(self, provider_id: str, status: ProviderHealthStatus) -> None:
        """Записать статус только для указанного provider_id."""
        self._status[provider_id] = status

    def get_status(self, provider_id: str) -> ProviderHealthStatus:
        """Прочитать статус; если не было записи — UNKNOWN."""
        return self._status.get(provider_id, ProviderHealthStatus.UNKNOWN)

    def is_healthy(self, provider_id: str) -> bool:
        """True если reachable или unknown (ещё не пробовали — не блокируем)."""
        status = self.get_status(provider_id)
        if status == ProviderHealthStatus.UNKNOWN:
            return True
        return status == ProviderHealthStatus.REACHABLE

    def is_unhealthy(self, provider_id: str) -> bool:
        """True если статус явно плохой."""
        return self.get_status(provider_id) in _UNHEALTHY

    def as_dict(self) -> dict[str, str]:
        """Снимок статусов для отладки (без секретов)."""
        return {key: value.value for key, value in self._status.items()}


def probe_ollama_tags(
    base_url: str,
    timeout_seconds: float = 3.0,
    headers: dict[str, str] | None = None,
) -> ProviderHealthStatus:
    """Read-only probe: GET {base_url}/api/tags без отправки page content.

    Не логирует заголовок Authorization и тело ответа с возможными секретами.
    """
    url = base_url.rstrip("/") + "/api/tags"
    # Копируем заголовки, но в исключениях/логах их не печатаем.
    request_headers = dict(headers or {})
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(url, headers=request_headers)
    except httpx.TimeoutException:
        return ProviderHealthStatus.TIMEOUT
    except httpx.TransportError:
        return ProviderHealthStatus.UNREACHABLE
    except Exception:
        # Любая неожиданная ошибка — unknown, без деталей в лог здесь.
        return ProviderHealthStatus.UNKNOWN

    if response.status_code == 401 or response.status_code == 403:
        return ProviderHealthStatus.AUTH_FAILED
    if response.status_code == 429:
        return ProviderHealthStatus.QUOTA_LIMITED
    if response.status_code >= 500:
        return ProviderHealthStatus.UNREACHABLE
    if response.status_code != 200:
        return ProviderHealthStatus.UNKNOWN

    # Успешный tags: reachable. model_missing проверяют отдельно по списку моделей.
    return ProviderHealthStatus.REACHABLE


def probe_ollama_tags_for_provider(
    store: ProviderHealthStore,
    provider_id: str,
    base_url: str,
    timeout_seconds: float = 3.0,
    headers: dict[str, str] | None = None,
) -> ProviderHealthStatus:
    """Probe одного провайдера и записать результат только в его ячейку store."""
    status = probe_ollama_tags(
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        headers=headers,
    )
    store.set_status(provider_id, status)
    return status


def mark_quota_limited(store: ProviderHealthStore, provider_id: str) -> None:
    """Пометить квоту только у одного provider_id (изоляция от соседей)."""
    store.set_status(provider_id, ProviderHealthStatus.QUOTA_LIMITED)
