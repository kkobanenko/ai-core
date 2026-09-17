"""Unit and mock integration tests for S2B Provider Transports."""

from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from unittest.mock import MagicMock

import pytest

import ai_core
from ai_core.errors import AiErrorKind
from ai_core.health import ProviderHealthStatus, ProviderHealthStore
from ai_core.provider_catalog import UnknownProviderIdentityError
from ai_core.routing import RouteCandidate
from ai_core.transports import (
    MistralTransport,
    OllamaTransport,
    ProviderTransport,
    TransportAttemptResult,
    TransportRequest,
    TransportResponse,
    TransportUsage,
    execute_transport_attempt,
    get_transport_for_candidate,
)


class MockServerHandler(BaseHTTPRequestHandler):
    """Configurable HTTP handler for mock provider testing."""

    response_status = 200
    response_body: dict[str, Any] = {}
    response_delay: float = 0.0
    received_requests: list[dict[str, Any]] = []

    def do_POST(self) -> None:
        content_len = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_len) if content_len > 0 else b""
        
        request_record = {
            "path": self.path,
            "headers": dict(self.headers),
            "body": json.loads(body_bytes.decode("utf-8")) if body_bytes else None,
        }
        self.received_requests.append(request_record)

        if self.response_delay > 0:
            time.sleep(self.response_delay)

        self.send_response(self.response_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(self.response_body).encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        # Silence standard HTTP request logging in test runs
        pass


@pytest.fixture
def mock_server():
    """Spin up an ephemeral mock HTTP server in a background daemon thread."""
    handler_class = type("DynamicHandler", (MockServerHandler,), {
        "response_status": 200,
        "response_body": {},
        "response_delay": 0.0,
        "received_requests": [],
    })

    # Pick an ephemeral free port
    server = HTTPServer(("127.0.0.1", 0), handler_class)
    host, port = server.server_address
    endpoint = f"http://{host}:{port}"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield endpoint, handler_class

    server.shutdown()
    server.server_close()


def test_ollama_transport_success(mock_server) -> None:
    endpoint, handler = mock_server
    handler.response_status = 200
    handler.response_body = {
        "message": {"role": "assistant", "content": "Привет из Ollama!"},
        "prompt_eval_count": 14,
        "eval_count": 28,
    }

    transport = OllamaTransport(default_endpoint=endpoint)
    candidate = RouteCandidate(provider_id="vm100_local_ollama", model="qwen2.5:7b")
    request = TransportRequest(
        candidate=candidate,
        messages=({"role": "user", "content": "Привет"},),
        temperature=0.2,
        timeout_seconds=5.0,
        extra_options={"num_ctx": 4096},
    )

    result = transport.send_attempt(request)

    assert result.ok is True
    assert result.error is None
    assert result.response is not None
    assert result.response.content == "Привет из Ollama!"
    assert result.response.usage == TransportUsage(
        prompt_tokens=14,
        completion_tokens=28,
        total_tokens=42,
    )
    assert result.latency_seconds > 0.0

    # Verify HTTP request on server
    assert len(handler.received_requests) == 1
    req = handler.received_requests[0]
    assert req["path"] == "/api/chat"
    assert req["body"]["model"] == "qwen2.5:7b"
    assert req["body"]["messages"] == [{"role": "user", "content": "Привет"}]
    assert req["body"]["stream"] is False
    assert req["body"]["options"]["temperature"] == 0.2
    assert req["body"]["options"]["num_ctx"] == 4096


def test_mistral_transport_success(mock_server) -> None:
    endpoint, handler = mock_server
    handler.response_status = 200
    handler.response_body = {
        "choices": [
            {"message": {"role": "assistant", "content": "Bonjour from Mistral!"}}
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
    }

    transport = MistralTransport(default_endpoint=endpoint)
    candidate = RouteCandidate(provider_id="mistral_external", model="mistral-large-latest")
    request = TransportRequest(
        candidate=candidate,
        messages=({"role": "user", "content": "Hello"},),
        temperature=0.5,
        api_key="secret-mistral-key",
        timeout_seconds=5.0,
    )

    result = transport.send_attempt(request)

    assert result.ok is True
    assert result.error is None
    assert result.response is not None
    assert result.response.content == "Bonjour from Mistral!"
    assert result.response.usage == TransportUsage(
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
    )

    # Verify Authorization header and path
    assert len(handler.received_requests) == 1
    req = handler.received_requests[0]
    assert req["path"] == "/v1/chat/completions"
    assert req["headers"].get("Authorization") == "Bearer secret-mistral-key"
    assert req["body"]["model"] == "mistral-large-latest"


@pytest.mark.parametrize(
    "status_code,expected_kind,expected_terminal,expected_fallback",
    [
        (429, AiErrorKind.RATE_LIMIT, False, True),
        (401, AiErrorKind.AUTH, True, False),
        (403, AiErrorKind.AUTH, True, False),
        (400, AiErrorKind.BAD_REQUEST, True, False),
        (404, AiErrorKind.NOT_FOUND, True, False),
        (500, AiErrorKind.SERVER, False, True),
        (502, AiErrorKind.SERVER, False, True),
        (503, AiErrorKind.SERVER, False, True),
    ],
)
def test_http_error_classification_and_single_attempt(
    mock_server,
    status_code: int,
    expected_kind: AiErrorKind,
    expected_terminal: bool,
    expected_fallback: bool,
) -> None:
    endpoint, handler = mock_server
    handler.response_status = status_code
    handler.response_body = {"error": f"Simulated error {status_code}"}

    transport = OllamaTransport(default_endpoint=endpoint)
    candidate = RouteCandidate(provider_id="gpu_ollama", model="deepseek-r1:8b")
    request = TransportRequest(
        candidate=candidate,
        messages=({"role": "user", "content": "Test"},),
        timeout_seconds=5.0,
    )

    result = transport.send_attempt(request)

    assert result.ok is False
    assert result.response is None
    assert result.error is not None
    assert result.error.kind == expected_kind
    assert result.error.status_code == status_code
    assert result.error.terminal == expected_terminal
    assert result.error.fallback_eligible == expected_fallback

    # CRITICAL INVARIANT: strictly one attempt made to server, no auto-retries!
    assert len(handler.received_requests) == 1


def test_transport_timeout(mock_server) -> None:
    endpoint, handler = mock_server
    handler.response_status = 200
    handler.response_delay = 0.5  # sleep longer than timeout

    transport = OllamaTransport(default_endpoint=endpoint)
    candidate = RouteCandidate(provider_id="vm100_local_ollama", model="llama3:8b")
    request = TransportRequest(
        candidate=candidate,
        messages=({"role": "user", "content": "Slow request"},),
        timeout_seconds=0.1,  # short deadline
    )

    result = transport.send_attempt(request)

    assert result.ok is False
    assert result.response is None
    assert result.error is not None
    assert result.error.kind == AiErrorKind.TIMEOUT
    assert result.error.retryable_same_provider is True
    assert result.error.fallback_eligible is True


def test_transport_connection_refused() -> None:
    # Use unused port on localhost that refuses connection
    unused_port = 59123
    transport = OllamaTransport(default_endpoint=f"http://127.0.0.1:{unused_port}")
    candidate = RouteCandidate(provider_id="vm100_local_ollama", model="llama3:8b")
    request = TransportRequest(
        candidate=candidate,
        messages=({"role": "user", "content": "Refused"},),
        timeout_seconds=1.0,
    )

    result = transport.send_attempt(request)

    assert result.ok is False
    assert result.response is None
    assert result.error is not None
    assert result.error.kind in (AiErrorKind.TRANSPORT, AiErrorKind.TIMEOUT, AiErrorKind.UNKNOWN)
    assert result.error.fallback_eligible is True


def test_get_transport_for_candidate_resolution() -> None:
    ollama_cands = [
        RouteCandidate(provider_id="vm100_local_ollama", model="qwen"),
        RouteCandidate(provider_id="gpu_ollama", model="qwen"),
        RouteCandidate(provider_id="ollama_cloud", model="qwen"),
    ]
    for c in ollama_cands:
        t = get_transport_for_candidate(c)
        assert isinstance(t, OllamaTransport)

    mistral_cand = RouteCandidate(provider_id="mistral_external", model="mistral-small")
    assert isinstance(get_transport_for_candidate(mistral_cand), MistralTransport)

    unknown_cand = RouteCandidate(provider_id="unregistered_provider", model="m")
    with pytest.raises(UnknownProviderIdentityError):
        get_transport_for_candidate(unknown_cand)


def test_execute_transport_attempt_health_store_integration(mock_server) -> None:
    endpoint, handler = mock_server
    health_store = ProviderHealthStore()

    candidate = RouteCandidate(provider_id="vm100_local_ollama", model="qwen2.5:7b")
    request = TransportRequest(
        candidate=candidate,
        messages=({"role": "user", "content": "Hi"},),
        endpoint=endpoint,
        timeout_seconds=5.0,
    )

    # 1. Success sets REACHABLE
    handler.response_status = 200
    handler.response_body = {"message": {"content": "OK"}}
    res1 = execute_transport_attempt(request, health_store=health_store)
    assert res1.ok is True
    assert health_store.get_status(candidate.provider_id, model=candidate.model) == ProviderHealthStatus.REACHABLE
    assert health_store.blocks_route(candidate.provider_id, model=candidate.model) is False

    # 2. 429 sets QUOTA_LIMITED
    handler.response_status = 429
    handler.response_body = {"error": "rate limit"}
    res2 = execute_transport_attempt(request, health_store=health_store)
    assert res2.ok is False
    assert health_store.get_status(candidate.provider_id, model=candidate.model) == ProviderHealthStatus.QUOTA_LIMITED
    assert health_store.blocks_route(candidate.provider_id, model=candidate.model) is True

    # 3. 500 sets UNREACHABLE
    handler.response_status = 500
    handler.response_body = {"error": "server error"}
    res3 = execute_transport_attempt(request, health_store=health_store)
    assert res3.ok is False
    assert health_store.get_status(candidate.provider_id, model=candidate.model) == ProviderHealthStatus.UNREACHABLE
    assert health_store.blocks_route(candidate.provider_id, model=candidate.model) is True


def test_root_api_contract_preserved() -> None:
    """Ensure adding transports did NOT modify root public API export."""
    expected_v01 = {
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
    assert set(ai_core.__all__) == expected_v01
