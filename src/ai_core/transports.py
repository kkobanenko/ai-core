"""S2B Provider Transports: Single-attempt HTTP execution over standard library urllib.

Architectural invariants:
- Single Fallback Owner: strictly ONE attempt per call; zero internal retry loops or nested fallbacks.
- Zero Heavy Dependencies: pure standard library urllib/json; no mandatory LangChain or third-party client SDKs.
- Error Classification: maps network/HTTP anomalies to ai_core.errors.ErrorDescriptor.
- Health Observation: feeds outcome observations to ProviderHealthStore without bypassing caller routing.
"""

from __future__ import annotations

import json
import math
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from ai_core.errors import (
    AiErrorKind,
    EgressNotAuthorizedError,
    ErrorDescriptor,
    classify_provider_error,
)
from ai_core.health import (
    ProviderHealthStatus,
    ProviderHealthStore,
)
from ai_core.privacy import DataClass, OutboundForm, is_egress_eligible
from ai_core.provider_catalog import (
    UnknownProviderIdentityError,
    get_provider_identity,
)
from ai_core.routing import RouteCandidate
from ai_core.tracing import record_llm_result, start_llm_span


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Fail-closed HTTP redirect handler preventing credential leakage across hops."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        return None


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
    # None сохраняет старое поведение: новые поля не поднимаются в корень.
    ollama_chat_fields: Mapping[str, Any] | None = None
    request_egress_authorized: bool = False
    # Те же поля, что у планировщика. Дефолт совпадает с ExecutionRequest.
    data_class: DataClass = DataClass.PUBLIC_NO_PII
    outbound_form: OutboundForm = OutboundForm.RAW


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


_THINK_UNSET = object()
_OLLAMA_RESERVED_EXTRA = frozenset(
    {"model", "messages", "stream", "think", "format", "keep_alive"}
)
_MAX_KEEP_ALIVE_SECONDS = 1800


def _valid_ollama_think(value: Any) -> bool:
    """Ollama think is bool, null, or a model-defined string. Numbers are rejected."""
    if isinstance(value, bool) or value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return bool(stripped) and "\n" not in value and "\r" not in value
    return False


_DURATION_PART = re.compile(r"^([0-9]+(?:\.[0-9]*)?|\.[0-9]+)(ns|us|µs|μs|ms|s|m|h)")
_DURATION_SCALE = {
    "ns": 1e-9,
    "us": 1e-6,
    "µs": 1e-6,
    "μs": 1e-6,
    "ms": 1e-3,
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
}


def _duration_seconds(text: str) -> float | None:
    """Разбор как у Go time.ParseDuration. Отрицательные значения запрещены."""
    if text.startswith("-") or not text:
        return None
    if text == "0":
        return 0.0
    rest = text
    total = 0.0
    found = False
    while rest:
        matched = _DURATION_PART.match(rest)
        if matched is None:
            return None
        total += float(matched.group(1)) * _DURATION_SCALE[matched.group(2)]
        rest = rest[matched.end() :]
        found = True
    if not found:
        return None
    return total


def _valid_keep_alive(value: Any) -> bool:
    """Число секунд или длительность Ollama. Потолок 30 минут. -1 запрещён."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        seconds = float(value)
    elif isinstance(value, str):
        parsed = _duration_seconds(value.strip())
        if parsed is None:
            return False
        seconds = parsed
    else:
        return False
    return 0 <= seconds <= _MAX_KEEP_ALIVE_SECONDS


def _json_size_ok(value: Any, depth: int) -> bool:
    """Любой JSON-serializable документ. Глубина и размер ограничены."""
    if depth > 32:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    if value is None or isinstance(value, (str, bool, int, float)):
        return True
    if isinstance(value, list):
        return all(_json_size_ok(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _json_size_ok(item, depth + 1) for key, item in value.items()
        )
    return False


def _valid_ollama_format(value: Any) -> bool:
    if value == "json":
        return True
    if not _json_size_ok(value, 0):
        return False
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return len(encoded) <= 65536


def _ollama_options_and_think(
    *,
    temperature: float,
    extra_options: Mapping[str, Any] | None,
    ollama_chat_fields: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], Any, Any, Any, str | None]:
    """Без opt-in extra_options целиком остаются в options, как до этого PR.

    ollama_chat_fields явно поднимает think, format и keep_alive в корень /api/chat.
    """
    options: dict[str, Any] = {"temperature": temperature}
    extra = dict(extra_options or {})
    options.update(extra)
    if ollama_chat_fields is None:
        return options, _THINK_UNSET, _THINK_UNSET, _THINK_UNSET, None
    fields = dict(ollama_chat_fields)
    think = fields.pop("think", _THINK_UNSET)
    chat_format = fields.pop("format", _THINK_UNSET)
    keep_alive = fields.pop("keep_alive", _THINK_UNSET)
    for key in ("think", "format", "keep_alive", "model", "messages", "stream"):
        options.pop(key, None)
    if fields:
        return options, _THINK_UNSET, _THINK_UNSET, _THINK_UNSET, "invalid ollama chat fields"
    if think is not _THINK_UNSET and not _valid_ollama_think(think):
        return options, _THINK_UNSET, _THINK_UNSET, _THINK_UNSET, "invalid think"
    if chat_format is not _THINK_UNSET and not _valid_ollama_format(chat_format):
        return options, think, _THINK_UNSET, _THINK_UNSET, "invalid format"
    if keep_alive is not _THINK_UNSET and not _valid_keep_alive(keep_alive):
        return options, think, chat_format, _THINK_UNSET, "invalid keep_alive"
    return options, think, chat_format, keep_alive, None


class OllamaTransport:
    """Single-attempt HTTP transport for Ollama-compatible APIs (/api/chat)."""

    DEFAULT_ENDPOINT = "http://127.0.0.1:11434"

    def __init__(
        self,
        default_endpoint: str | None = None,
        *,
        authenticated_cloud: bool = False,
    ) -> None:
        self._default_endpoint = default_endpoint or self.DEFAULT_ENDPOINT
        # Opt-in only: legacy OllamaTransport callers retain identical behavior.
        self._authenticated_cloud = authenticated_cloud

    def send_attempt(
        self,
        request: TransportRequest,
    ) -> TransportAttemptResult:
        start_time = time.perf_counter()
        base_endpoint = (request.endpoint or self._default_endpoint).rstrip("/")
        url = f"{base_endpoint}/api/chat"

        # Direct cloud inference is a distinct EXTERNAL trust boundary. Do not
        # send a bearer token to an operator-supplied or redirected endpoint.
        cloud_headers: dict[str, str] = {}
        if request.candidate.provider_id == "ollama_cloud" and self._authenticated_cloud:
            parsed = urllib.parse.urlparse(base_endpoint)
            if (
                parsed.scheme != "https"
                or parsed.hostname != "ollama.com"
                or parsed.port not in (None, 443)
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in ("", "/")
                or parsed.query
                or parsed.fragment
            ):
                return TransportAttemptResult(
                    candidate=request.candidate,
                    response=None,
                    error=ErrorDescriptor(AiErrorKind.BAD_REQUEST, None, False, False, True),
                    latency_seconds=time.perf_counter() - start_time,
                )
            if request.request_egress_authorized is not True:
                return TransportAttemptResult(
                    candidate=request.candidate,
                    response=None,
                    error=ErrorDescriptor(AiErrorKind.AUTH, None, False, False, True),
                    latency_seconds=time.perf_counter() - start_time,
                )
            api_key = request.api_key or os.environ.get("OLLAMA_API_KEY", "")
            if not api_key or "\r" in api_key or "\n" in api_key:
                return TransportAttemptResult(
                    candidate=request.candidate,
                    response=None,
                    error=ErrorDescriptor(AiErrorKind.AUTH, None, False, False, True),
                    latency_seconds=time.perf_counter() - start_time,
                )
            cloud_headers["Authorization"] = f"Bearer {api_key}"

        options, think, chat_format, keep_alive, root_error = _ollama_options_and_think(
            temperature=request.temperature,
            extra_options=request.extra_options,
            ollama_chat_fields=request.ollama_chat_fields,
        )
        if root_error is not None:
            return TransportAttemptResult(
                candidate=request.candidate,
                response=None,
                error=ErrorDescriptor(AiErrorKind.BAD_REQUEST, None, False, False, True),
                latency_seconds=time.perf_counter() - start_time,
            )

        payload = {
            "model": request.candidate.model,
            "messages": [dict(m) for m in request.messages],
            "stream": False,
            "options": options,
        }
        # Локальный /api/chat. Cloud structured output — другой контракт, format туда не кладём.
        local_chat = request.candidate.provider_id != "ollama_cloud"
        if think is not _THINK_UNSET:
            payload["think"] = think
        if local_chat and chat_format is not _THINK_UNSET:
            payload["format"] = chat_format
        if local_chat and keep_alive is not _THINK_UNSET:
            payload["keep_alive"] = keep_alive

        req_bytes = json.dumps(payload).encode("utf-8")
        http_req = urllib.request.Request(
            url=url,
            data=req_bytes,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                **cloud_headers,
            },
            method="POST",
        )

        try:
            opener = urllib.request.build_opener(NoRedirectHandler)
            with opener.open(
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

        payload: dict[str, Any] = {}
        if request.extra_options:
            # Prevent extra_options from hijacking governing model or messages
            payload.update(
                {
                    k: v
                    for k, v in request.extra_options.items()
                    if k not in ("model", "messages", "stream", "think", "format", "keep_alive")
                }
            )
        payload["model"] = request.candidate.model
        payload["messages"] = [dict(m) for m in request.messages]
        payload["temperature"] = request.temperature

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
            opener = urllib.request.build_opener(NoRedirectHandler)
            with opener.open(
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

    if candidate.provider_id == "vm100_local_ollama":
        endpoint = default_ollama_endpoint or os.environ.get(
            "AI_CORE_VM100_OLLAMA_ENDPOINT", OllamaTransport.DEFAULT_ENDPOINT
        )
        return OllamaTransport(default_endpoint=endpoint)

    if candidate.provider_id == "gpu_ollama":
        endpoint = default_ollama_endpoint or os.environ.get(
            "AI_CORE_GPU_OLLAMA_ENDPOINT", "http://127.0.0.1:11435"
        )
        return OllamaTransport(default_endpoint=endpoint)

    if candidate.provider_id == "ollama_cloud":
        # The existing route and default endpoint are intentionally unchanged.
        # Direct authenticated cloud inference is a separate explicit runtime opt-in.
        direct_auth = os.environ.get("AI_CORE_OLLAMA_CLOUD_AUTH_MODE") == "direct"
        endpoint = default_ollama_endpoint or os.environ.get(
            "AI_CORE_OLLAMA_CLOUD_ENDPOINT",
            "https://ollama.com" if direct_auth else "https://api.ollama.com",
        )
        return OllamaTransport(default_endpoint=endpoint, authenticated_cloud=direct_auth)

    if candidate.provider_id == "mistral_external":
        return MistralTransport(default_endpoint=default_mistral_endpoint)

    raise UnknownProviderIdentityError(candidate.provider_id)


def is_local_loopback_endpoint(endpoint: Any) -> bool:
    """Return True if endpoint strictly targets a local loopback interface."""
    if not endpoint or not isinstance(endpoint, str):
        return True
    try:
        parsed = urllib.parse.urlparse(endpoint)
        hostname = (parsed.hostname or "").lower().strip()
        return hostname in ("127.0.0.1", "localhost", "::1", "0.0.0.0")
    except Exception:
        return False


def execute_transport_attempt(
    request: TransportRequest,
    *,
    transport: ProviderTransport | None = None,
    health_store: ProviderHealthStore | None = None,
) -> TransportAttemptResult:
    """Execute strictly one attempt against the candidate, recording health observations."""
    resolved_transport = transport or get_transport_for_candidate(request.candidate)
    raw_endpoint = request.endpoint or getattr(resolved_transport, "_default_endpoint", None)
    target_endpoint = raw_endpoint if isinstance(raw_endpoint, str) else None

    identity = get_provider_identity(request.candidate.provider_id)
    # Планировщик и транспорт вызывают одну функцию.
    # SECRET запрещён. INTERNAL_TRUSTED и LOCAL_SAME_HOST не требуют флаг.
    # EXTERNAL и UNKNOWN_BOUNDARY требуют буквальный True.
    privacy_allows = is_egress_eligible(
        data_class=request.data_class,
        outbound_form=request.outbound_form,
        network_boundary=identity.network_boundary,
        request_egress_authorized=request.request_egress_authorized,
    )
    # Подмена endpoint на чужой хост остаётся запрещённой без literal True.
    # Правило одинаковое для LOCAL_SAME_HOST и INTERNAL_TRUSTED.
    endpoint_stays_on_loopback = is_local_loopback_endpoint(target_endpoint)
    endpoint_allows = (
        endpoint_stays_on_loopback or request.request_egress_authorized is True
    )
    if not privacy_allows or not endpoint_allows:
        raise EgressNotAuthorizedError(
            f"External network egress not authorized for provider '{request.candidate.provider_id}' "
            f"(target endpoint '{target_endpoint}' requires egress authorization)"
        )

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
