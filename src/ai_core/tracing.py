"""Инициализация Phoenix OTEL и безопасный lifecycle helper для LLM spans."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any

from ai_core.attributes import AttributeValue, sanitize_attributes
from ai_core.config import load_phoenix_config
from ai_core.io_policy import maybe_truncate

_logger = logging.getLogger(__name__)
_tracer: Any = None
_provider: Any = None
_initialized = False


def init_tracing(project_name: str | None = None) -> object | None:
    """Инициализировать Phoenix tracing в soft-fail режиме."""
    global _tracer, _provider, _initialized
    if _initialized:
        return _tracer

    cfg = load_phoenix_config()
    if not cfg.enabled:
        _initialized = True
        return None

    name = (project_name or cfg.project_name or "").strip()
    if not name:
        _logger.warning("PHOENIX project name is empty; tracing disabled")
        _initialized = True
        return None

    try:
        from phoenix.otel import register

        # Конфигурируем exporter один раз и сохраняем provider для мягкого flush
        # на shutdown, не раскрывая endpoint или детали ошибки в логах.
        _provider = register(
            project_name=name,
            endpoint=cfg.collector_endpoint,
            protocol="http/protobuf",
            batch=True,
        )
        _tracer = _provider.get_tracer("ai-core")
        _logger.info("Phoenix tracing enabled for project=%s", name)
    except Exception as error:
        _logger.warning("Phoenix tracing initialization failed: %s", type(error).__name__)
        _provider = None
        _tracer = None
    _initialized = True
    return _tracer


def shutdown_tracing() -> None:
    """Мягко сбросить буфер exporter, если provider был инициализирован."""
    if _provider is None:
        return
    try:
        _provider.force_flush()
    except Exception as error:  # shutdown остаётся soft-fail
        _logger.warning("phoenix force_flush failed: %s", type(error).__name__)


class _SoftSpanContext(AbstractContextManager[object | None]):
    """Контекст span, который никогда не ломает consumer-код."""

    def __init__(
        self,
        *,
        workflow: str,
        attributes: dict[str, AttributeValue],
        system_prompt: str,
        user_prompt: str,
    ) -> None:
        self.workflow = workflow
        self.attributes = attributes
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self._inner: AbstractContextManager[Any] | None = None
        self._span: Any = None

    def __enter__(self) -> object | None:
        if _tracer is None:
            return None
        try:
            self._inner = _tracer.start_as_current_span(f"llm.{self.workflow}")
            self._span = self._inner.__enter__()
        except Exception as error:
            _logger.warning("Phoenix span start failed: %s", type(error).__name__)
            self._inner = None
            self._span = None
            return None

        try:
            for key, value in self.attributes.items():
                self._span.set_attribute(key, value)

            cfg = load_phoenix_config()
            if cfg.trace_include_io:
                if self.system_prompt:
                    self._span.set_attribute(
                        "llm.input.system",
                        maybe_truncate(self.system_prompt, cfg.max_io_chars),
                    )
                if self.user_prompt:
                    self._span.set_attribute(
                        "llm.input.user",
                        maybe_truncate(self.user_prompt, cfg.max_io_chars),
                    )
        except Exception as error:
            _logger.warning("Phoenix span attributes failed: %s", type(error).__name__)
        return self._span

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if self._inner is not None:
            try:
                self._inner.__exit__(exc_type, exc, traceback)
            except Exception as error:
                _logger.warning("Phoenix span close failed: %s", type(error).__name__)
        return False


def start_llm_span(
    *,
    workflow: str,
    attributes: Mapping[str, AttributeValue] | None = None,
    system_prompt: str = "",
    user_prompt: str = "",
) -> AbstractContextManager[object | None]:
    """Создать безопасный LLM span context только с allowlist-метаданными."""
    safe = sanitize_attributes({**(attributes or {}), "workflow": workflow})
    return _SoftSpanContext(
        workflow=workflow,
        attributes=safe,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


def record_llm_result(
    span: object | None,
    *,
    response_text: str = "",
    status: str,
    latency_ms: int | None = None,
    fallback_mode: str | None = None,
    error_type: str | None = None,
) -> None:
    """Записать результат LLM-вызова в span, не ломая consumer-код."""
    if span is None:
        return
    try:
        result_attributes = sanitize_attributes(
            {
                "status": status,
                "latency_ms": latency_ms,
                "fallback_mode": fallback_mode,
                "error_type": error_type,
            }
        )
        for key, value in result_attributes.items():
            span.set_attribute(key, value)

        cfg = load_phoenix_config()
        if cfg.trace_include_io and response_text:
            span.set_attribute(
                "llm.output",
                maybe_truncate(response_text, cfg.max_io_chars),
            )
    except Exception as error:  # tracing не должен прерывать бизнес-логику
        _logger.warning("phoenix record_llm_result failed: %s", type(error).__name__)
