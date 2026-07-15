"""Конфигурация Phoenix observability из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _read_bool(name: str, default: bool) -> bool:
    """Прочитать булеву переменную окружения."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_int(name: str, default: int) -> int:
    """Прочитать целочисленную переменную окружения."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw.strip())


@dataclass(frozen=True)
class PhoenixConfig:
    """Настройки подключения к Phoenix и политики IO в трейсах."""

    enabled: bool
    collector_endpoint: str
    project_name: str
    trace_include_io: bool
    max_io_chars: int


def load_phoenix_config() -> PhoenixConfig:
    """Загрузить конфигурацию Phoenix из переменных окружения.

    Переменные:
    - PHOENIX_ENABLED — главный переключатель (по умолчанию false)
    - PHOENIX_COLLECTOR_ENDPOINT — OTLP HTTP endpoint
    - PHOENIX_PROJECT_NAME — имя проекта в Phoenix UI
    - PHOENIX_TRACE_INCLUDE_IO — прикреплять обрезанные prompt/response
    - PHOENIX_TRACE_MAX_IO_CHARS — лимит символов на поле IO
    """
    return PhoenixConfig(
        enabled=_read_bool("PHOENIX_ENABLED", default=False),
        collector_endpoint=os.environ.get(
            "PHOENIX_COLLECTOR_ENDPOINT",
            "http://127.0.0.1:6006/v1/traces",
        ),
        project_name=os.environ.get("PHOENIX_PROJECT_NAME", ""),
        trace_include_io=_read_bool("PHOENIX_TRACE_INCLUDE_IO", default=False),
        max_io_chars=_read_int("PHOENIX_TRACE_MAX_IO_CHARS", default=4000),
    )
