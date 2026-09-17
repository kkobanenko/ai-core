"""S2B Provider Transports: Single-attempt HTTP execution over standard library urllib.

Architectural invariants:
- Single Fallback Owner: strictly ONE attempt per call; zero internal retry loops or nested fallbacks.
- Zero Heavy Dependencies: pure standard library urllib/json; no mandatory LangChain or third-party client SDKs.
- Error Classification: maps network/HTTP anomalies to ai_core.errors.ErrorDescriptor.
- Health Observation: feeds outcome observations to ProviderHealthStore without bypassing caller routing.
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from ai_core.errors import (
    AiErrorKind,
    ErrorDescriptor,
    classify_provider_error,
)
from ai_core.health import (
    ProviderHealthStatus,
    ProviderHealthStore,
)
from ai_core.provider_catalog import (
    UnknownProviderIdentityError,
    get_provider_identity,
)
from ai_core.routing import RouteCandidate
from ai_core.tracing import record_llm_result, start_llm_span


@dataclass(frozen=True)
class TransportRequest:
    """Request payload and execution boundaries for a single provider attempt."""

    candidate: RouteCandidate
    messages: tuple[Mapping[str, str], ...]
    temperature: float = 0.7
    timeout_seconds: float = 30.0
    endpoint: str | None = None
    api_key: str | None = None
    extra_options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransportUsage:
    """Token accounting metadata when reported by the upstream provider."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class TransportResponse:
    """Successful provider response data from a single attempt."""

    candidate: RouteCandidate
    content: str
    usage: TransportUsage
    latency_seconds: float
    raw_response: Mapping[str, Any]


@dataclass(frozen=True)
class TransportAttemptResult:
    """Outcome of a single transport attempt: strictly one of response or error."""

    candidate: RouteCandidate
    response: TransportResponse | None
    error: ErrorDescriptor | None
    latency_seconds: float

    @property
    def ok(self) -> bool:
        return self.response is not None and self.error is None


class ProviderTransport(Protocol):
    """Protocol for a single-attempt provider transport."""

    def send_attempt(
        self,
        request: TransportRequest,
    ) -> TransportAttemptResult:
        """Execute strictly one attempt against the target provider endpoint."""
        ...


class OllamaTransport:
    """Single-attempt HTTP transport for Ollama-compatible APIs (/api/chat)."""

    DEFAULT_ENDPOINT = "http://127.0.0.1:11434"

    def __init__(self, default_endpoint: str | None = None) -> None:
        self._default_endpoint = default_endpoint or self.DEFAULT_ENDPOINT

    def send_attempt(
        self,
        request: TransportRequest,
    ) -> TransportAttemptResult:
        start_time = time.perf_counter()
        base_endpoint = (request.endpoint or self._default_endpoint).rstrip("/")
        url = f"{base_endpoint}/api/chat"

        options: dict[str, Any] = {"temperature": request.temperature}
        if request.extra_options:
            options.update(dict(request.extra_options))

        payload = {
            "model": request.candidate.model,
            "messages": [dict(m) for m in request.messages],
            "stream": False,
            "options": options,
        }

        req_bytes = json.dumps(payload).encode("utf-8")
        http_req = urllib.request.Request(
            url=url,
            data=req_bytes,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                http_req,
                timeout=request.timeout_seconds,
            ) as response:
                status_code = response.status
                raw_bytes = response.read()
                raw_json = json.loads(raw_bytes.decode("utf-8"))

            latency = time.perf_counter() - start_time
            content = raw_json.get("message", {}).get("content", "")

            prompt_tokens = raw_json.get("prompt_eval_count")
            completion_tokens = raw_json.get("eval_count")
            total_tokens = (
                (prompt_tokens + completion_tokens)
                if (prompt_tokens is not None and completion_tokens is not None)
                else None
            )
            usage = TransportUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )

            return TransportAttemptResult(
                candidate=request.candidate,
                response=TransportResponse(
                    candidate=request.candidate,
                    content=content,
                    usage=usage,
                    latency_seconds=latency,
                    raw_response=raw_json,
                ),
                error=None,
                latency_seconds=latency,
            )
        except Exception as exc:
            latency = time.perf_counter() - start_time
            descriptor = _classify_transport_exception(exc)
            return TransportAttemptResult(
                candidate=request.candidate,
                response=None,
                error=descriptor,
                latency_seconds=latency,
            )


class MistralTransport:
    """Single-attempt HTTP transport for Mistral/OpenAI completions API (/v1/chat/completions)."""

    DEFAULT_ENDPOINT = "https://api.mistral.ai"

    def __init__(self, default_endpoint: str | None = None) -> None:
        self._default_endpoint = default_endpoint or self.DEFAULT_ENDPOINT

    def send_attempt(
        self,
        request: TransportRequest,
    ) -> TransportAttemptResult:
        start_time = time.perf_counter()
        base_endpoint = (request.endpoint or self._default_endpoint).rstrip("/")
        url = f"{base_endpoint}/v1/chat/completions"

        api_key = request.api_key or os.environ.get("MISTRAL_API_KEY", "")

        payload: dict[str, Any] = {
            "model": request.candidate.model,
            "messages": [dict(m) for m in request.messages],
            "temperature": request.temperature,
        }
        if request.extra_options:
            payload.update(dict(request.extra_options))

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req_bytes = json.dumps(payload).encode("utf-8")
        http_req = urllib.request.Request(
            url=url,
            data=req_bytes,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                http_req,
                timeout=request.timeout_seconds,
            ) as response:
                raw_bytes = response.read()
                raw_json = json.loads(raw_bytes.decode("utf-8"))

            latency = time.perf_counter() - start_time
            choices = raw_json.get("choices", [])
            content = (
                choices[0].get("message", {}).get("content", "")
                if choices
                else ""
            )

            raw_usage = raw_json.get("usage", {})
            usage = TransportUsage(
                prompt_tokens=raw_usage.get("prompt_tokens"),
                completion_tokens=raw_usage.get("completion_tokens"),
                total_tokens=raw_usage.get("total_tokens"),
            )

            return TransportAttemptResult(
                candidate=request.candidate,
                response=TransportResponse(
                    candidate=request.candidate,
                    content=content,
                    usage=usage,
                    latency_seconds=latency,
                    raw_response=raw_json,
                ),
                error=None,
                latency_seconds=latency,
            )
        except Exception as exc:
            latency = time.perf_counter() - start_time
            descriptor = _classify_transport_exception(exc)
            return TransportAttemptResult(
                candidate=request.candidate,
                response=None,
                error=descriptor,
                latency_seconds=latency,
            )


def _classify_transport_exception(exc: BaseException) -> ErrorDescriptor:
    """Map raw transport exceptions to ErrorDescriptor."""
    if isinstance(exc, urllib.error.HTTPError):
        return classify_provider_error(exc)

    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return ErrorDescriptor(
                AiErrorKind.TIMEOUT,
                None,
                retryable_same_provider=True,
                fallback_eligible=True,
                terminal=False,
            )
        return classify_provider_error(reason if isinstance(reason, BaseException) else exc)

    if isinstance(exc, (socket.timeout, TimeoutError)):
        return ErrorDescriptor(
            AiErrorKind.TIMEOUT,
            None,
            retryable_same_provider=True,
            fallback_eligible=True,
            terminal=False,
        )

    if isinstance(exc, json.JSONDecodeError):
        return ErrorDescriptor(
            AiErrorKind.TRANSPORT,
            None,
            retryable_same_provider=False,
            fallback_eligible=True,
            terminal=False,
        )

    return classify_provider_error(exc)


def get_transport_for_candidate(
    candidate: RouteCandidate,
    *,
    default_ollama_endpoint: str | None = None,
    default_mistral_endpoint: str | None = None,
) -> ProviderTransport:
    """Resolve the appropriate ProviderTransport implementation for a canonical provider identity."""
    # Ensure candidate provider is valid in catalog
    get_provider_identity(candidate.provider_id)

    if candidate.provider_id in ("vm100_local_ollama", "gpu_ollama", "ollama_cloud"):
        return OllamaTransport(default_endpoint=default_ollama_endpoint)

    if candidate.provider_id == "mistral_external":
        return MistralTransport(default_endpoint=default_mistral_endpoint)

    raise UnknownProviderIdentityError(candidate.provider_id)


def execute_transport_attempt(
    request: TransportRequest,
    *,
    transport: ProviderTransport | None = None,
    health_store: ProviderHealthStore | None = None,
) -> TransportAttemptResult:
    """Execute strictly one attempt against the candidate, recording health observations."""
    resolved_transport = transport or get_transport_for_candidate(request.candidate)

    # Extract prompts from messages for tracing (soft-fail: default to empty).
    system_prompt = ""
    user_prompt = ""
    for msg in request.messages:
        role = msg.get("role", "")
        if role == "system" and not system_prompt:
            system_prompt = msg.get("content", "")
        elif role == "user" and not user_prompt:
            user_prompt = msg.get("content", "")

    with start_llm_span(
        workflow=f"transport.{request.candidate.provider_id}",
        attributes={
            "provider_id": request.candidate.provider_id,
            "model": request.candidate.model,
            "timeout_seconds": request.timeout_seconds,
            "temperature": request.temperature,
        },
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    ) as span:
        result = resolved_transport.send_attempt(request)

        # Record outcome into the span (soft-fail via record_llm_result internals).
        if result.ok:
            record_llm_result(
                span,
                status="ok",
                response_text=result.response.content if result.response else "",
                latency_ms=int(result.latency_seconds * 1000),
            )
        else:
            record_llm_result(
                span,
                status="error",
                latency_ms=int(result.latency_seconds * 1000),
                error_type=result.error.kind.value if result.error else "unknown",
            )

    if health_store is not None:
        if result.ok:
            health_store.set_status(
                request.candidate.provider_id,
                ProviderHealthStatus.REACHABLE,
                model=request.candidate.model,
            )
        elif result.error is not None:
            health_status = _error_kind_to_health_status(result.error.kind)
            health_store.set_status(
                request.candidate.provider_id,
                health_status,
                model=request.candidate.model,
            )

    return result


def _error_kind_to_health_status(kind: AiErrorKind) -> ProviderHealthStatus:
    """Translate normalized AiErrorKind to ProviderHealthStatus observation."""
    if kind == AiErrorKind.TIMEOUT:
        return ProviderHealthStatus.TIMEOUT
    if kind == AiErrorKind.RATE_LIMIT:
        return ProviderHealthStatus.QUOTA_LIMITED
    if kind == AiErrorKind.AUTH:
        return ProviderHealthStatus.AUTH_FAILED
    if kind == AiErrorKind.NOT_FOUND:
        return ProviderHealthStatus.MODEL_MISSING
    if kind in (AiErrorKind.SERVER, AiErrorKind.TRANSPORT, AiErrorKind.PROVIDER_UNAVAILABLE):
        return ProviderHealthStatus.UNREACHABLE
    return ProviderHealthStatus.UNKNOWN


__all__ = [
    "MistralTransport",
    "OllamaTransport",
    "ProviderTransport",
    "TransportAttemptResult",
    "TransportRequest",
    "TransportResponse",
    "TransportUsage",
    "execute_transport_attempt",
    "get_transport_for_candidate",
]
