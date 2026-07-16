"""Безопасная allowlist-политика для span-метаданных."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias

AttributeValue: TypeAlias = str | bool | int | float

# Разрешаем только заранее согласованные ключи, чтобы в span не попали
# чувствительные данные вроде email, URL, токенов или произвольных payload.
ALLOWED_ATTRIBUTE_KEYS = frozenset(
    {
        "workflow",
        "adapter",
        "provider_id",
        "model",
        "latency_ms",
        "status",
        "error_type",
        "fallback_mode",
        "actor_role",
        "request_id",
    }
)


def sanitize_attributes(
    attributes: Mapping[str, object] | None,
) -> dict[str, AttributeValue]:
    """Оставить только allowlist-ключи со скалярными значениями."""
    safe: dict[str, AttributeValue] = {}
    for key, value in (attributes or {}).items():
        if key not in ALLOWED_ATTRIBUTE_KEYS:
            continue
        if isinstance(value, (str, bool, int, float)):
            safe[key] = value
    return safe
