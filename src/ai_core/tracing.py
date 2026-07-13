"""Инициализация Phoenix OTEL и helper для LLM spans."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from ai_core.config import load_phoenix_config
from ai_core.io_policy import maybe_truncate

_logger = logging.getLogger(__name__)

# Глобальный tracer; None — tracing выключен или init не удался.
_tracer = None
# Флаг идемпотентности: повторный init_tracing не трогает OTEL.
_initialized = False


def init_tracing(project_name: str | None = None) -> Any:
    """Зарегистрировать Phoenix tracer.

    При PHOENIX_ENABLED=false — no-op.
    Ошибки регистрации логируются, вызывающий код не должен падать.
    Повторные вызовы безопасны (idempotent).
    """
    global _tracer, _initialized

    if _initialized:
        return _tracer

    cfg = load_phoenix_config()
    if not cfg.enabled:
        _initialized = True
        return None

    name = (project_name or cfg.project_name or "").strip()
    if not name:
        _logger.warning("PHOENIX_ENABLED but PHOENIX_PROJECT_NAME empty; skip tracing")
        _initialized = True
        return None

    try:
        from phoenix.otel import register

        provider = register(
            project_name=name,
            endpoint=cfg.collector_endpoint,
            protocol="http/protobuf",
            batch=True,
        )
        _tracer = provider.get_tracer("ai-core")
        _initialized = True
        _logger.info(
            "phoenix tracing enabled project=%s endpoint=%s",
            name,
            cfg.collector_endpoint,
        )
        return _tracer
    except Exception as error:
        _logger.warning("phoenix init_tracing failed: %s", error)
        _initialized = True
        _tracer = None
        return None


def shutdown_tracing() -> None:
    """Заглушка для симметрии API (batch exporter flush при необходимости)."""
    return None


@contextmanager
def start_llm_span(
    *,
    workflow: str,
    attributes: dict[str, Any] | None = None,
    system_prompt: str = "",
    user_prompt: str = "",
    response_text: str = "",
) -> Iterator[Any]:
    """Контекст LLM span.

    Если tracer не инициализирован — yield None без исключения.
    IO-атрибуты пишутся при PHOENIX_TRACE_INCLUDE_IO=true (с обрезкой).
    """
    attrs = dict(attributes or {})
    attrs["workflow"] = workflow
    cfg = load_phoenix_config()

    if _tracer is None:
        yield None
        return

    with _tracer.start_as_current_span(f"llm.{workflow}") as span:
        for key, value in attrs.items():
            if value is None:
                continue
            span.set_attribute(str(key), value)

        if cfg.trace_include_io:
            if system_prompt:
                span.set_attribute(
                    "llm.input.system",
                    maybe_truncate(system_prompt, cfg.max_io_chars),
                )
            if user_prompt:
                span.set_attribute(
                    "llm.input.user",
                    maybe_truncate(user_prompt, cfg.max_io_chars),
                )
            if response_text:
                span.set_attribute(
                    "llm.output",
                    maybe_truncate(response_text, cfg.max_io_chars),
                )

        yield span
