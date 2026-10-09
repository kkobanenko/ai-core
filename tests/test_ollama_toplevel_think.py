"""Ollama /api/chat must receive think at the JSON root, never inside options."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from ai_core.errors import AiErrorKind
from ai_core.routing import RouteCandidate
from ai_core.transports import MistralTransport, OllamaTransport, TransportRequest


class _Handler(BaseHTTPRequestHandler):
    received: list[dict[str, Any]] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        body = json.loads(raw.decode("utf-8")) if raw else None
        self.received.append({"path": self.path, "body": body})
        payload = {"message": {"role": "assistant", "content": "ok"}, "eval_count": 1}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        return


def _server():
    handler = type("H", (_Handler,), {"received": []})
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}", handler


def _request(extra: dict[str, Any] | None) -> TransportRequest:
    return TransportRequest(
        candidate=RouteCandidate("gpu_ollama", "qwen3.6:35b"),
        messages=({"role": "user", "content": "ping"},),
        temperature=0.7,
        timeout_seconds=5.0,
        extra_options=extra,
    )


def test_think_false_is_top_level_and_not_inside_options() -> None:
    server, endpoint, handler = _server()
    try:
        result = OllamaTransport(default_endpoint=endpoint).send_attempt(
            _request({"think": False, "num_predict": 40, "num_ctx": 2048})
        )
        body = handler.received[0]["body"]
        assert result.ok is True
        assert body["think"] is False
        assert "think" not in body["options"]
        assert body["options"]["temperature"] == 0.7
        assert body["options"]["num_predict"] == 40
        assert body["options"]["num_ctx"] == 2048
        assert body["stream"] is False
        assert body["model"] == "qwen3.6:35b"
    finally:
        server.shutdown()


def test_think_true_is_top_level() -> None:
    server, endpoint, handler = _server()
    try:
        OllamaTransport(default_endpoint=endpoint).send_attempt(_request({"think": True}))
        body = handler.received[0]["body"]
        assert body["think"] is True
        assert "think" not in body["options"]
    finally:
        server.shutdown()


def test_omitted_think_keeps_previous_payload_shape() -> None:
    server, endpoint, handler = _server()
    try:
        OllamaTransport(default_endpoint=endpoint).send_attempt(_request({"num_predict": 8}))
        body = handler.received[0]["body"]
        assert "think" not in body
        assert body["options"] == {"temperature": 0.7, "num_predict": 8}
    finally:
        server.shutdown()


def test_invalid_think_is_rejected_without_http() -> None:
    server, endpoint, handler = _server()
    try:
        result = OllamaTransport(default_endpoint=endpoint).send_attempt(_request({"think": 1}))
        assert result.ok is False
        assert result.error is not None
        assert result.error.kind is AiErrorKind.BAD_REQUEST
        assert handler.received == []
    finally:
        server.shutdown()


def test_extra_options_cannot_replace_model_messages_or_stream() -> None:
    server, endpoint, handler = _server()
    try:
        OllamaTransport(default_endpoint=endpoint).send_attempt(
            _request(
                {
                    "model": "evil",
                    "messages": [{"role": "user", "content": "injected"}],
                    "stream": True,
                    "think": False,
                }
            )
        )
        body = handler.received[0]["body"]
        assert body["model"] == "qwen3.6:35b"
        assert body["messages"] == [{"role": "user", "content": "ping"}]
        assert body["stream"] is False
        assert body["think"] is False
    finally:
        server.shutdown()


def test_mistral_does_not_receive_ollama_think() -> None:
    server, endpoint, handler = _server()
    try:
        request = TransportRequest(
            candidate=RouteCandidate("mistral_external", "mistral-small-latest"),
            messages=({"role": "user", "content": "ping"},),
            temperature=0.2,
            timeout_seconds=5.0,
            api_key="test-key",
            extra_options={"think": False, "max_tokens": 16},
        )
        MistralTransport(default_endpoint=endpoint).send_attempt(request)
        body = handler.received[0]["body"]
        assert "think" not in body
        assert body["max_tokens"] == 16
        assert body["model"] == "mistral-small-latest"
    finally:
        server.shutdown()
