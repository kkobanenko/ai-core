"""Тесты soft-fail инициализации Phoenix tracing и LLM span helper."""

from unittest.mock import MagicMock

from ai_core.tracing import (
    init_tracing,
    record_llm_result,
    shutdown_tracing,
    start_llm_span,
)


def test_init_tracing_noop_when_disabled(monkeypatch):
    """При PHOENIX_ENABLED=false init_tracing — no-op, возвращает None."""
    monkeypatch.setenv("PHOENIX_ENABLED", "false")
    assert init_tracing(project_name="prozakupki-platform") is None


def test_start_llm_span_noop_when_not_initialized(monkeypatch):
    """start_llm_span не падает, если tracing выключен или не инициализирован."""
    monkeypatch.setenv("PHOENIX_ENABLED", "false")
    init_tracing(project_name="x")
    with start_llm_span(workflow="classify", attributes={"model": "m"}) as span:
        assert span is None or hasattr(span, "set_attribute")


def test_record_result_sets_only_explicit_result_fields(monkeypatch):
    monkeypatch.setenv("PHOENIX_TRACE_INCLUDE_IO", "false")
    span = MagicMock()
    record_llm_result(span, status="ok", latency_ms=25, fallback_mode="ai")
    span.set_attribute.assert_any_call("status", "ok")
    span.set_attribute.assert_any_call("latency_ms", 25)
    span.set_attribute.assert_any_call("fallback_mode", "ai")


def test_shutdown_force_flush_is_soft(monkeypatch):
    provider = MagicMock()
    provider.force_flush.side_effect = RuntimeError("collector down")
    monkeypatch.setattr("ai_core.tracing._provider", provider)
    shutdown_tracing()
    provider.force_flush.assert_called_once()


def test_span_omits_io_when_metadata_only(monkeypatch):
    span = MagicMock()
    inner = MagicMock()
    inner.__enter__.return_value = span
    inner.__exit__.return_value = False
    tracer = MagicMock()
    tracer.start_as_current_span.return_value = inner
    monkeypatch.setattr("ai_core.tracing._tracer", tracer)
    monkeypatch.setenv("PHOENIX_TRACE_INCLUDE_IO", "false")
    with start_llm_span(
        workflow="chat",
        system_prompt="SYSTEM_SENTINEL",
        user_prompt="USER_SENTINEL",
    ):
        pass
    keys = [call.args[0] for call in span.set_attribute.call_args_list]
    assert "llm.input.system" not in keys
    assert "llm.input.user" not in keys


def test_span_truncates_opt_in_io(monkeypatch):
    span = MagicMock()
    inner = MagicMock()
    inner.__enter__.return_value = span
    inner.__exit__.return_value = False
    tracer = MagicMock()
    tracer.start_as_current_span.return_value = inner
    monkeypatch.setattr("ai_core.tracing._tracer", tracer)
    monkeypatch.setenv("PHOENIX_TRACE_INCLUDE_IO", "true")
    monkeypatch.setenv("PHOENIX_TRACE_MAX_IO_CHARS", "20")
    with start_llm_span(workflow="eval", user_prompt="x" * 100):
        pass
    value = next(
        call.args[1]
        for call in span.set_attribute.call_args_list
        if call.args[0] == "llm.input.user"
    )
    assert len(value) == 20
    assert value.endswith("…[truncated]")
