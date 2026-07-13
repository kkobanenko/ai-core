"""Тесты soft-fail инициализации Phoenix tracing и LLM span helper."""

from ai_core.tracing import init_tracing, shutdown_tracing, start_llm_span


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
