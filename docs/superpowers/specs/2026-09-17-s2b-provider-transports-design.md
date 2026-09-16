# AI Core S2B Provider Transports Design

**Date:** 2026-09-17  
**Status:** DESIGN ONLY / NO IMPLEMENTATION AUTHORIZED PENDING PLATFORM-CONTROL GOVERNANCE GATE  
**Initiative:** `ai-core-v0.3-design` (Stage S2B)  
**Base:** `main@b62de3efb5072046fa4bb819c9eec1e56b46e3e5` (current main with S1, S2A, C3 v2, Coordinator v0.2)

---

## 1. Goal

Define a clean, dependency-light transport interface that executes a **single attempt** against an authorized `RouteCandidate` (`vm100_local_ollama`, `gpu_ollama`, `ollama_cloud`, `mistral_external`) without violating single-fallback-owner principles or adding heavy framework dependencies.

---

## 2. Core Architectural Principles & Boundaries

### 2.1 Single Fallback Owner
* As specified in `platform-control/config/compatibility.yaml`:
  * `single_fallback_owner_required: true`
  * `nested_fallback_forbidden: true`
* `PrivacyAwareRouter` (C3 v2) plans the candidate order (`RoutePlan.eligible`).
* S2B Transport executes **strictly one attempt** against one candidate.
* S2B **does NOT**:
  - run an automatic retry loop;
  - silently switch to a fallback provider;
  - spawn nested fallbacks;
  - perform speculative concurrent requests;
  - bypass caller-directed fallback workflows.
* If an attempt fails, S2B returns normalized error metadata (`ErrorDescriptor`), updates health observations (`ProviderHealthStore`), and returns control to the caller/consumer who owns the workflow loop.

### 2.2 Dependency Minimization
* Core `ai-core` will **not** depend on LangChain, LlamaIndex, or heavy third-party agent frameworks.
* Transports are implemented using Python standard library (`urllib.request`) with optional extras for high-throughput environments (e.g. `ai-core[httpx]`).
* Existing projects (Prozakupki, Zoom, Clin-rec) retain their own internal adapters without version conflicts.

### 2.3 Integration with Existing Contracts
* **Provider Identity (S1)**: Transports are keyed to canonical provider IDs (`vm100_local_ollama`, `gpu_ollama`, `ollama_cloud`, `mistral_external`).
* **Privacy & Egress (S1)**: Transports verify that a candidate has passed privacy planning before issuing network bytes.
* **Error Classification (C3 v2)**: Transport network/HTTP exceptions are mapped to `ai_core.errors.ErrorDescriptor` via `classify_provider_error()`.
* **Budget & Timeout (C3 v2)**: Request socket timeouts are derived strictly from `AttemptBudget.timeout_for_attempt()`.
* **Health Observation (C3 v2)**: Successful or failed calls record observations into `ProviderHealthStore.record_success()` or `record_failure()`.
* **Observability (v0.1 / v0.2)**: Single-attempt spans are recorded under Phoenix OpenTelemetry tracing, respecting `io_policy.maybe_truncate`.

---

## 3. Data Contracts

```python
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol
from ai_core.routing import RouteCandidate
from ai_core.errors import ErrorDescriptor

@dataclass(frozen=True)
class TransportRequest:
    candidate: RouteCandidate
    messages: tuple[Mapping[str, str], ...]
    temperature: float = 0.7
    timeout_seconds: float = 30.0
    extra_options: Mapping[str, Any] = ()

@dataclass(frozen=True)
class TransportUsage:
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

@dataclass(frozen=True)
class TransportResponse:
    candidate: RouteCandidate
    content: str
    usage: TransportUsage
    latency_seconds: float
    raw_response: Mapping[str, Any]

@dataclass(frozen=True)
class TransportAttemptResult:
    candidate: RouteCandidate
    response: Optional[TransportResponse]
    error: Optional[ErrorDescriptor]
    latency_seconds: float

    @property
    def ok(self) -> bool:
        return self.response is not None and self.error is None
```

---

## 4. Transport Protocols & Implementation Strategy

```python
class ProviderTransport(Protocol):
    def send_attempt(
        self,
        request: TransportRequest,
    ) -> TransportAttemptResult:
        """Execute exactly one HTTP call to the provider endpoint."""
        ...
```

### 4.1 Supported Transports
1. **Ollama HTTP Transport** (`/api/chat`):
   - Handles `vm100_local_ollama`, `gpu_ollama`, `ollama_cloud`.
   - Formats payload according to Ollama native API.
   - Preserves streaming capability flags where configured.
2. **Mistral HTTP Transport** (`/v1/chat/completions`):
   - Handles `mistral_external`.
   - Passes standard OpenAI-compatible completions format.
   - Extracts authorization header from configured environment variable (`MISTRAL_API_KEY`).

---

## 5. Governance Gate & Implementation Roadmap

1. **Gate**: Platform-Control RFC / Issue approval required before any code is added to `src/ai_core/`.
2. **Phase 1 (Tests)**: Test harness with mock HTTP server simulating timeout, 429 rate limit, 500 server error, and valid completion.
3. **Phase 2 (Code)**: `src/ai_core/transports.py` with standard library urllib/http implementation.
4. **Phase 3 (Observability)**: Instrumentation wrapping `ai_core.tracing.start_llm_span`.
