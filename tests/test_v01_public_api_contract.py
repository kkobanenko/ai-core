"""Контракт публичного API линии v0.1 (tracing-only), как на main / tag v0.1.0.

Эти тесты фиксируют поверхность, от которой зависит Zoom (`record_llm_result`).
Они не импортируют провайдерный API v0.2 и не начинают реализацию v0.3.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import ai_core
import ai_core.tracing as tracing_mod
from ai_core import (
    AttributeValue,
    PhoenixConfig,
    init_tracing,
    load_phoenix_config,
    maybe_truncate,
    record_llm_result,
    sanitize_attributes,
    shutdown_tracing,
    start_llm_span,
)
from ai_core.attributes import ALLOWED_ATTRIBUTE_KEYS


def _isolate_disabled_phoenix(monkeypatch) -> None:
    """Явно выключить Phoenix и сбросить module-level кэш tracing.

    Без этого тест зависит от порядка: если раньше init_tracing уже выставил
    _initialized/_tracer при другом PHOENIX_ENABLED, soft-fail assertion врёт.
    monkeypatch восстанавливает env и атрибуты модуля после теста.
    """
    monkeypatch.setenv("PHOENIX_ENABLED", "false")
    monkeypatch.setattr(tracing_mod, "_initialized", False)
    monkeypatch.setattr(tracing_mod, "_tracer", None)
    monkeypatch.setattr(tracing_mod, "_provider", None)


def test_public_all_matches_v01_surface() -> None:
    """Публичный __all__ должен оставаться tracing/v0.1-совместимым на этой ветке."""
    expected = {
        "AttributeValue",
        "PhoenixConfig",
        "init_tracing",
        "load_phoenix_config",
        "maybe_truncate",
        "record_llm_result",
        "sanitize_attributes",
        "shutdown_tracing",
        "start_llm_span",
    }
    assert set(ai_core.__all__) == expected


def test_v02_provider_symbols_absent_on_main_line() -> None:
    """Пока v0.2 не смержен в main, провайдерные символы отсутствуют."""
    for name in (
        "LangChainJsonClient",
        "ProviderConfig",
        "build_chat_model",
        "ProviderTransportError",
        "JsonCompletion",
        "AttemptRecord",
    ):
        assert not hasattr(ai_core, name)


def test_zoom_required_record_llm_result_callable() -> None:
    """Zoom импортирует record_llm_result из ai_core — символ обязан существовать."""
    assert callable(record_llm_result)
    assert callable(start_llm_span)
    assert callable(init_tracing)
    assert callable(shutdown_tracing)


def test_v01_attribute_allowlist_stable() -> None:
    """Allowlist v0.1 не должен молча совпасть с llm.* ключами v0.2."""
    assert "provider_id" in ALLOWED_ATTRIBUTE_KEYS
    assert "model" in ALLOWED_ATTRIBUTE_KEYS
    assert "llm.provider" not in ALLOWED_ATTRIBUTE_KEYS
    safe = sanitize_attributes(
        {
            "provider_id": "ollama",
            "api_key": "secret",
            "llm.provider": "should-drop",
            "http.url": "http://example",
        }
    )
    assert safe == {"provider_id": "ollama"}


def test_phoenix_defaults_deterministic(monkeypatch) -> None:
    """Конфиг Phoenix детерминирован env defaults."""
    monkeypatch.delenv("PHOENIX_ENABLED", raising=False)
    monkeypatch.delenv("PHOENIX_TRACE_INCLUDE_IO", raising=False)
    monkeypatch.delenv("PHOENIX_TRACE_MAX_IO_CHARS", raising=False)
    monkeypatch.delenv("PHOENIX_COLLECTOR_ENDPOINT", raising=False)
    monkeypatch.delenv("PHOENIX_PROJECT_NAME", raising=False)
    cfg = load_phoenix_config()
    assert isinstance(cfg, PhoenixConfig)
    assert cfg.enabled is False
    assert cfg.trace_include_io is False
    assert cfg.max_io_chars == 4000
    assert cfg.collector_endpoint == "http://127.0.0.1:6006/v1/traces"
    assert cfg.project_name == ""


def test_disabled_tracing_soft_fail(monkeypatch) -> None:
    """При выключенном Phoenix span-API не падает.

    Precondition задаётся явно: PHOENIX_ENABLED=false + чистый tracing cache.
    """
    _isolate_disabled_phoenix(monkeypatch)
    assert init_tracing() is None
    with start_llm_span(workflow="validation", attributes={"provider_id": "x"}) as span:
        assert span is None
        record_llm_result(span, status="ok", latency_ms=1, response_text="n/a")
    shutdown_tracing()


def test_disabled_tracing_order_independent(monkeypatch) -> None:
    """Disabled-path стабилен после parent env PHOENIX_ENABLED=true и грязного кэша.

    Регрессия: полный suite раньше маскировал флейк, потому что соседний тест
    инициализировал cache при disabled. Здесь сначала загрязняем состояние
    (enabled + stale tracer), затем изолируем disabled-path заново.
    """
    # 1) Имитация «родительского» окружения и уже прогретого кэша.
    monkeypatch.setenv("PHOENIX_ENABLED", "true")
    monkeypatch.setattr(tracing_mod, "_initialized", True)
    monkeypatch.setattr(tracing_mod, "_tracer", MagicMock(name="stale_tracer"))
    monkeypatch.setattr(tracing_mod, "_provider", MagicMock(name="stale_provider"))
    # Без изоляции init_tracing вернул бы stale_tracer — это и есть баг порядка.
    assert init_tracing() is not None

    # 2) Правильная изоляция disabled-path: env=false + сброс кэша.
    _isolate_disabled_phoenix(monkeypatch)
    assert init_tracing() is None
    with start_llm_span(workflow="validation", attributes={"provider_id": "x"}) as span:
        assert span is None
        record_llm_result(span, status="ok", latency_ms=1, response_text="n/a")
    shutdown_tracing()


def test_truncate_policy() -> None:
    """IO truncate сохраняет bounded length."""
    assert maybe_truncate(None, 10) is None
    assert maybe_truncate("hi", 10) == "hi"
    out = maybe_truncate("abcdefghij", 8)
    assert out is not None
    assert len(out) <= 8


def test_attribute_value_type_alias_exported() -> None:
    """AttributeValue остаётся частью публичного контракта v0.1."""
    assert AttributeValue is not None
