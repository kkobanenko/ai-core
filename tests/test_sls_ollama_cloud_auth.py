"""Offline contract tests for direct Ollama Cloud transport.

No live network calls or credentials are used.
"""

from __future__ import annotations

import json
import urllib.request

from ai_core.errors import AiErrorKind
from ai_core.routing import RouteCandidate
from ai_core.transports import OllamaTransport, TransportRequest, get_transport_for_candidate


_CLOUD = RouteCandidate(provider_id="ollama_cloud", model="gpt-oss:20b-cloud")


class _FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(
            {
                "message": {"content": "Three short suggestions"},
                "prompt_eval_count": 8,
                "eval_count": 12,
            }
        ).encode("utf-8")


class _FakeOpener:
    def __init__(self):
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return _FakeResponse()


def _req(*, egress=True, api_key=None):
    return TransportRequest(
        candidate=_CLOUD,
        messages=({"role": "user", "content": "hello"},),
        request_egress_authorized=egress,
        api_key=api_key,
        timeout_seconds=3.0,
    )


def test_cloud_default_host_is_official_endpoint(monkeypatch):
    monkeypatch.delenv("AI_CORE_OLLAMA_CLOUD_ENDPOINT", raising=False)
    transport = get_transport_for_candidate(_CLOUD)
    assert transport._default_endpoint == "https://ollama.com"


def test_cloud_without_egress_or_key_is_fail_closed(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    opener = _FakeOpener()
    monkeypatch.setattr(urllib.request, "build_opener", lambda *_: opener)
    transport = get_transport_for_candidate(_CLOUD)

    denied = transport.send_attempt(_req(egress=False, api_key="fake-key"))
    assert not denied.ok and denied.error.kind == AiErrorKind.AUTH
    assert denied.error.terminal is True

    no_key = transport.send_attempt(_req(egress=True))
    assert not no_key.ok and no_key.error.kind == AiErrorKind.AUTH
    assert no_key.error.fallback_eligible is False
    assert opener.requests == []


def test_cloud_key_never_sent_to_untrusted_endpoint(monkeypatch):
    opener = _FakeOpener()
    monkeypatch.setattr(urllib.request, "build_opener", lambda *_: opener)
    for endpoint in ("http://ollama.com", "https://evil.invalid", "https://ollama.com.evil.invalid"):
        transport = OllamaTransport(default_endpoint=endpoint)
        result = transport.send_attempt(_req(api_key="example-only-not-secret"))
        assert not result.ok and result.error.kind == AiErrorKind.BAD_REQUEST
    assert opener.requests == []


def test_cloud_uses_bearer_and_single_request(monkeypatch):
    opener = _FakeOpener()
    monkeypatch.setattr(urllib.request, "build_opener", lambda *_: opener)
    transport = get_transport_for_candidate(_CLOUD)

    result = transport.send_attempt(_req(api_key="example-only-not-secret"))
    assert result.ok
    assert result.response.content == "Three short suggestions"
    assert result.response.usage.total_tokens == 20
    assert len(opener.requests) == 1
    request, timeout = opener.requests[0]
    assert request.full_url == "https://ollama.com/api/chat"
    assert request.get_header("Authorization") == "Bearer example-only-not-secret"
    assert timeout == 3.0


def test_cloud_resolves_key_from_environment(monkeypatch):
    opener = _FakeOpener()
    monkeypatch.setattr(urllib.request, "build_opener", lambda *_: opener)
    monkeypatch.setenv("OLLAMA_API_KEY", "env-example-only-not-secret")
    result = get_transport_for_candidate(_CLOUD).send_attempt(_req())
    assert result.ok
    request, _ = opener.requests[0]
    assert request.get_header("Authorization") == "Bearer env-example-only-not-secret"
