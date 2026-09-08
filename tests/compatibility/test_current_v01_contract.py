from __future__ import annotations

import inspect
import logging
from contextlib import AbstractContextManager
from dataclasses import fields

import ai_core
import ai_core.tracing as tracing


EXPECTED_SIGNATURES = {
    "init_tracing": "(project_name: 'str | None' = None) -> 'object | None'",
    "load_phoenix_config": "() -> 'PhoenixConfig'",
    "maybe_truncate": "(text: 'str | None', max_chars: 'int') -> 'str | None'",
    "record_llm_result": (
        "(span: 'object | None', *, response_text: 'str' = '', status: 'str', "
        "latency_ms: 'int | None' = None, fallback_mode: 'str | None' = None, "
        "error_type: 'str | None' = None) -> 'None'"
    ),
    "sanitize_attributes": (
        "(attributes: 'Mapping[str, object] | None') -> 'dict[str, AttributeValue]'"
    ),
    "shutdown_tracing": "() -> 'None'",
    "start_llm_span": (
        "(*, workflow: 'str', attributes: 'Mapping[str, AttributeValue] | None' = None, "
        "system_prompt: 'str' = '', user_prompt: 'str' = '') -> "
        "'AbstractContextManager[object | None]'"
    ),
}


class SecretBearingError(RuntimeError):
    pass


class _RecordingSpan:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


class _SpanContext(AbstractContextManager[_RecordingSpan]):
    def __init__(self, span: _RecordingSpan) -> None:
        self.span = span

    def __enter__(self) -> _RecordingSpan:
        return self.span

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False


class _RecordingTracer:
    def __init__(self, span: _RecordingSpan) -> None:
        self.span = span

    def start_as_current_span(self, name: str) -> _SpanContext:
        assert name == "llm.compatibility"
        return _SpanContext(self.span)


def _reset_tracing(monkeypatch) -> None:
    monkeypatch.setattr(tracing, "_initialized", False)
    monkeypatch.setattr(tracing, "_tracer", None)
    monkeypatch.setattr(tracing, "_provider", None)


def test_existing_v01_contract_is_extended_with_exact_signatures() -> None:
    assert {
        name: str(inspect.signature(getattr(ai_core, name)))
        for name in EXPECTED_SIGNATURES
    } == EXPECTED_SIGNATURES


def test_phoenix_config_public_shape_is_frozen_and_ordered() -> None:
    assert ai_core.PhoenixConfig.__dataclass_params__.frozen is True
    assert [field.name for field in fields(ai_core.PhoenixConfig)] == [
        "enabled",
        "collector_endpoint",
        "project_name",
        "trace_include_io",
        "max_io_chars",
    ]


def test_init_failure_is_soft_and_does_not_log_exception_text(
    monkeypatch,
    caplog,
) -> None:
    import phoenix.otel

    _reset_tracing(monkeypatch)
    monkeypatch.setenv("PHOENIX_ENABLED", "true")
    monkeypatch.setenv("PHOENIX_PROJECT_NAME", "compatibility")
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "https://secret.example/?token=leak")

    def fail_register(**kwargs):
        raise SecretBearingError("credential=do-not-log")

    monkeypatch.setattr(phoenix.otel, "register", fail_register)
    with caplog.at_level(logging.WARNING, logger="ai_core.tracing"):
        assert ai_core.init_tracing() is None

    text = caplog.text
    assert "SecretBearingError" in text
    assert "do-not-log" not in text
    assert "secret.example" not in text
    assert "token=leak" not in text


def test_span_io_is_default_off_and_only_allowlisted_metadata_is_recorded(
    monkeypatch,
) -> None:
    span = _RecordingSpan()
    monkeypatch.setattr(tracing, "_tracer", _RecordingTracer(span))
    monkeypatch.setenv("PHOENIX_TRACE_INCLUDE_IO", "false")

    with ai_core.start_llm_span(
        workflow="compatibility",
        attributes={"provider_id": "vm100_local_ollama", "api_key": "secret"},
        system_prompt="system-secret",
        user_prompt="user-secret",
    ) as active_span:
        assert active_span is span
        ai_core.record_llm_result(
            active_span,
            response_text="response-secret",
            status="ok",
            latency_ms=4,
        )

    assert span.attributes == {
        "workflow": "compatibility",
        "provider_id": "vm100_local_ollama",
        "status": "ok",
        "latency_ms": 4,
    }


def test_span_start_and_shutdown_failures_are_soft_and_metadata_only(
    monkeypatch,
    caplog,
) -> None:
    class BrokenTracer:
        def start_as_current_span(self, name: str):
            raise SecretBearingError("prompt=do-not-log")

    class BrokenProvider:
        def force_flush(self) -> None:
            raise SecretBearingError("endpoint=do-not-log")

    monkeypatch.setattr(tracing, "_tracer", BrokenTracer())
    monkeypatch.setattr(tracing, "_provider", BrokenProvider())

    with caplog.at_level(logging.WARNING, logger="ai_core.tracing"):
        with ai_core.start_llm_span(workflow="compatibility") as span:
            assert span is None
        ai_core.shutdown_tracing()

    assert caplog.text.count("SecretBearingError") == 2
    assert "do-not-log" not in caplog.text


def test_record_failure_is_soft_and_does_not_log_payload(monkeypatch, caplog) -> None:
    class BrokenSpan:
        def set_attribute(self, key: str, value: object) -> None:
            raise SecretBearingError("payload=do-not-log")

    with caplog.at_level(logging.WARNING, logger="ai_core.tracing"):
        ai_core.record_llm_result(
            BrokenSpan(),
            response_text="response-secret",
            status="failed",
        )

    assert "SecretBearingError" in caplog.text
    assert "do-not-log" not in caplog.text
    assert "response-secret" not in caplog.text
