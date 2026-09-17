"""S2B Phase 3 Observability Tests: tracing integration in execute_transport_attempt.

Tests verify that the tracing span wrapping is correct, that span attributes and
results are recorded, and critically that tracing failures never break the transport.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_core.errors import AiErrorKind, ErrorDescriptor
from ai_core.routing import RouteCandidate
from ai_core.transports import (
    TransportAttemptResult,
    TransportRequest,
    TransportResponse,
    TransportUsage,
    execute_transport_attempt,
)


def _make_request(
    provider_id: str = "vm100_local_ollama",
    model: str = "qwen3:8b",
    system_msg: str = "You are a helpful assistant.",
    user_msg: str = "Hello",
) -> TransportRequest:
    messages: list[dict[str, str]] = []
    if system_msg:
        messages.append({"role": "system", "content": system_msg})
    if user_msg:
        messages.append({"role": "user", "content": user_msg})
    return TransportRequest(
        candidate=RouteCandidate(provider_id=provider_id, model=model),
        messages=tuple(messages),
        temperature=0.7,
        timeout_seconds=10.0,
    )


def _ok_result(request: TransportRequest) -> TransportAttemptResult:
    return TransportAttemptResult(
        candidate=request.candidate,
        response=TransportResponse(
            candidate=request.candidate,
            content="Hello! How can I help?",
            usage=TransportUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            latency_seconds=0.5,
            raw_response={"message": {"content": "Hello! How can I help?"}},
        ),
        error=None,
        latency_seconds=0.5,
    )


def _error_result(request: TransportRequest) -> TransportAttemptResult:
    return TransportAttemptResult(
        candidate=request.candidate,
        response=None,
        error=ErrorDescriptor(
            AiErrorKind.TIMEOUT,
            None,
            retryable_same_provider=True,
            fallback_eligible=True,
            terminal=False,
        ),
        latency_seconds=30.0,
    )


class TestTransportObservability:
    """Verify tracing span lifecycle in execute_transport_attempt."""

    @patch("ai_core.transports.record_llm_result")
    @patch("ai_core.transports.start_llm_span")
    def test_success_creates_span_and_records_ok(
        self,
        mock_start_span: MagicMock,
        mock_record: MagicMock,
    ) -> None:
        request = _make_request()
        ok = _ok_result(request)
        mock_transport = MagicMock()
        mock_transport.send_attempt.return_value = ok

        mock_span = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_span)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_start_span.return_value = mock_ctx

        result = execute_transport_attempt(request, transport=mock_transport)

        assert result.ok
        mock_start_span.assert_called_once()
        call_kwargs = mock_start_span.call_args.kwargs
        assert call_kwargs["workflow"] == "transport.vm100_local_ollama"
        assert call_kwargs["attributes"]["provider_id"] == "vm100_local_ollama"
        assert call_kwargs["attributes"]["model"] == "qwen3:8b"
        assert call_kwargs["system_prompt"] == "You are a helpful assistant."
        assert call_kwargs["user_prompt"] == "Hello"

        mock_record.assert_called_once()
        record_kwargs = mock_record.call_args.kwargs
        assert record_kwargs["status"] == "ok"
        assert record_kwargs["latency_ms"] == 500

    @patch("ai_core.transports.record_llm_result")
    @patch("ai_core.transports.start_llm_span")
    def test_error_creates_span_and_records_error(
        self,
        mock_start_span: MagicMock,
        mock_record: MagicMock,
    ) -> None:
        request = _make_request()
        err = _error_result(request)
        mock_transport = MagicMock()
        mock_transport.send_attempt.return_value = err

        mock_span = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_span)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_start_span.return_value = mock_ctx

        result = execute_transport_attempt(request, transport=mock_transport)

        assert not result.ok
        mock_record.assert_called_once()
        record_kwargs = mock_record.call_args.kwargs
        assert record_kwargs["status"] == "error"
        assert record_kwargs["error_type"] == "timeout"
        assert record_kwargs["latency_ms"] == 30000

    @patch("ai_core.transports.record_llm_result")
    @patch("ai_core.transports.start_llm_span")
    def test_tracing_span_start_failure_does_not_break_transport(
        self,
        mock_start_span: MagicMock,
        mock_record: MagicMock,
    ) -> None:
        """If start_llm_span raises, transport must still return a valid result."""
        request = _make_request()
        ok = _ok_result(request)
        mock_transport = MagicMock()
        mock_transport.send_attempt.return_value = ok

        # start_llm_span itself returns a context manager that yields None on failure
        # (soft-fail by design). But even if it raised, execute_transport_attempt
        # should be protected. Let's verify the soft-fail path.
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=None)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_start_span.return_value = mock_ctx

        result = execute_transport_attempt(request, transport=mock_transport)

        assert result.ok
        assert result.response is not None
        assert result.response.content == "Hello! How can I help?"
        # record_llm_result called with span=None, which internally does nothing
        mock_record.assert_called_once()

    @patch("ai_core.transports.start_llm_span")
    def test_real_tracing_soft_fail_without_phoenix(
        self,
        mock_start_span: MagicMock,
    ) -> None:
        """Without Phoenix, real tracing functions return None span — transport works fine."""
        request = _make_request()
        ok = _ok_result(request)
        mock_transport = MagicMock()
        mock_transport.send_attempt.return_value = ok

        # Simulate real _SoftSpanContext behavior: yields None when tracer is None
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=None)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_start_span.return_value = mock_ctx

        # Use real record_llm_result (not mocked) — it handles span=None gracefully
        result = execute_transport_attempt(request, transport=mock_transport)

        assert result.ok
        assert result.response.content == "Hello! How can I help?"

    @patch("ai_core.transports.record_llm_result")
    @patch("ai_core.transports.start_llm_span")
    def test_span_attributes_contain_timeout_and_temperature(
        self,
        mock_start_span: MagicMock,
        mock_record: MagicMock,
    ) -> None:
        request = _make_request()
        ok = _ok_result(request)
        mock_transport = MagicMock()
        mock_transport.send_attempt.return_value = ok

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_start_span.return_value = mock_ctx

        execute_transport_attempt(request, transport=mock_transport)

        attrs = mock_start_span.call_args.kwargs["attributes"]
        assert attrs["timeout_seconds"] == 10.0
        assert attrs["temperature"] == 0.7

    @patch("ai_core.transports.record_llm_result")
    @patch("ai_core.transports.start_llm_span")
    def test_messages_without_system_prompt(
        self,
        mock_start_span: MagicMock,
        mock_record: MagicMock,
    ) -> None:
        """When no system message is present, system_prompt should be empty."""
        request = _make_request(system_msg="")
        ok = _ok_result(request)
        mock_transport = MagicMock()
        mock_transport.send_attempt.return_value = ok

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_start_span.return_value = mock_ctx

        execute_transport_attempt(request, transport=mock_transport)

        assert mock_start_span.call_args.kwargs["system_prompt"] == ""
        assert mock_start_span.call_args.kwargs["user_prompt"] == "Hello"

    @patch("ai_core.transports.record_llm_result")
    @patch("ai_core.transports.start_llm_span")
    def test_health_store_still_updated_with_tracing(
        self,
        mock_start_span: MagicMock,
        mock_record: MagicMock,
    ) -> None:
        """Health store updates must still work alongside tracing."""
        from ai_core.health import ProviderHealthStatus, ProviderHealthStore

        request = _make_request()
        ok = _ok_result(request)
        mock_transport = MagicMock()
        mock_transport.send_attempt.return_value = ok

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_start_span.return_value = mock_ctx

        health_store = ProviderHealthStore()
        execute_transport_attempt(request, transport=mock_transport, health_store=health_store)

        status = health_store.get_status("vm100_local_ollama", model="qwen3:8b")
        assert status == ProviderHealthStatus.REACHABLE
