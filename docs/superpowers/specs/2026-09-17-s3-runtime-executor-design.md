# AI Core S3 Runtime & Executor Architecture Design

**Date:** 2026-09-17  
**Status:** DESIGN ONLY / NO IMPLEMENTATION AUTHORIZED PENDING PLATFORM-CONTROL GOVERNANCE GATE  
**Initiative:** `ai-core-v0.3-design` (Stage S3)  
**Base:** `main@0d57df924f3d40c7eb2f475f6e6826e652ad9162` (v0.2.3 milestone: S1, S2A, C3 v2, Coordinator v0.2, S2B transports + observability)

---

## 1. Goal

Define a robust, deterministic **Single-Loop Runtime** and developer-friendly **Executor Facade** that orchestrates the complete flow:
`PrivacyAwareRouter` (planning) → `AttemptBudget` (deadline accounting) → `ProviderTransport` (execution) → `ProviderHealthStore` (observation).

This closes the gap between raw transport primitives and consumer application ergonomics, providing a single-call interface while maintaining strict single-fallback-owner and fail-closed privacy guarantees.

---

## 2. Core Architectural Invariants

### 2.1 Single Fallback Owner
* As mandated in `platform-control/config/compatibility.yaml`:
  * `single_fallback_owner_required: true`
  * `nested_fallback_forbidden: true`
* `SingleLoopRuntime` is the **sole owner** of the fallback loop:
  - It iterates linearly across `RoutePlan.eligible` candidates in the exact priority order established by routing policy.
  - Individual transports execute strictly one attempt with zero internal retries or recursion.
  - Fallback is triggered **only** when an attempt yields an `ErrorDescriptor` where `fallback_eligible is True`.
  - Terminal or non-fallback errors (e.g., validation failure, privacy policy refusal) abort the loop immediately without trying further candidates.

### 2.2 Strict Time Budget Management
* Every execution is bounded by an `AttemptBudget`:
  - Total request deadline is enforced across all candidate attempts.
  - Before each attempt, `budget.timeout_for_attempt(...)` calculates the available slice.
  - If available time is below `budget.min_attempt_seconds`, the loop halts with `RequestDeadlineExceededError`.
  - Timeouts prevent cascading latency or hanging callers when primary providers are degraded.

### 2.3 Comprehensive Attempt Telemetry & Diagnostics
* The caller always receives full visibility into what happened:
  - On success: `ExecutionResult` contains the final `TransportResponse`, the winning `RouteCandidate`, total elapsed seconds, and the sequence of prior failed attempts (`tuple[TransportAttemptResult, ...]`).
  - On complete exhaustion: `AllCandidatesExhaustedError` is raised, encapsulating all accumulated `TransportAttemptResult` descriptors so consumers can log or diagnose why each provider failed.

### 2.4 High-Level Developer Ergonomics (Executor Facade)
* Applications should not need to manually construct routers, policies, budgets, and loop engines for standard calls.
* The `Executor` module exposes high-level functions:
  - `execute_chat(messages, ...)`
  - `execute_prompt(prompt, ...)`
* Sensible defaults are provided:
  - Default candidate order: `vm100_local_ollama` → `gpu_ollama` → `mistral_external`
  - Default capability: `ProviderCapability.CHAT`
  - Default privacy: internal boundary only unless egress is explicitly authorized
  - Default total timeout: 30.0 seconds

---

## 3. Data Contracts

```python
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence
from ai_core.budget import AttemptBudget
from ai_core.capabilities import ProviderCapability
from ai_core.health import ProviderHealthStore
from ai_core.privacy import DataClass, OutboundForm
from ai_core.routing import RouteCandidate, RoutePlan, RoutePolicy
from ai_core.transports import (
    ProviderTransport,
    TransportAttemptResult,
    TransportRequest,
    TransportResponse,
)

@dataclass(frozen=True)
class ExecutionRequest:
    """High-level request input to the runtime execution engine."""
    messages: tuple[Mapping[str, str], ...]
    candidates: tuple[RouteCandidate, ...]
    capability: ProviderCapability = ProviderCapability.CHAT
    data_class: DataClass = DataClass.INTERNAL_DATA
    outbound_form: OutboundForm = OutboundForm.RAW
    total_timeout_seconds: float = 30.0
    temperature: float = 0.7
    extra_options: Mapping[str, Any] = field(default_factory=dict)
    request_egress_authorized: bool = False

@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of a successful multi-candidate execution loop."""
    response: TransportResponse
    winner: RouteCandidate
    attempts: tuple[TransportAttemptResult, ...]
    total_latency_seconds: float

    @property
    def content(self) -> str:
        return self.response.content

    @property
    def fallback_occurred(self) -> bool:
        return len(self.attempts) > 1
```

---

## 4. Error Hierarchy & Decision Matrix

```
AiError
├── NoEligibleProviderError (raised when router rejects all candidates before execution)
├── RequestDeadlineExceededError (raised when total budget expires before or during attempts)
└── AllCandidatesExhaustedError (raised when all eligible candidates failed with fallback-eligible errors)
```

### Fallback Decision Matrix:
| `AiErrorKind` | `fallback_eligible` | Runtime Behavior |
|---|---|---|
| `TIMEOUT` | `True` | Update health → Proceed to next candidate |
| `RATE_LIMIT` (429) | `True` | Update health → Proceed to next candidate |
| `SERVER` (5xx) | `True` | Update health → Proceed to next candidate |
| `TRANSPORT` / Connection Refused | `True` | Update health → Proceed to next candidate |
| `PROVIDER_UNAVAILABLE` | `True` | Update health → Proceed to next candidate |
| `AUTH` (401/403) | `False` | Terminal: raise immediately (misconfiguration) |
| `NOT_FOUND` (404 model missing) | `True` | Update health → Proceed to next candidate |
| `INVALID_INPUT` (400 bad request) | `False` | Terminal: raise immediately (caller prompt issue) |

---

## 5. Runtime Algorithm (SingleLoopRuntime)

```python
class SingleLoopRuntime:
    """Deterministic single-loop executor over planned route candidates."""

    def __init__(
        self,
        health_store: Optional[ProviderHealthStore] = None,
        transport_resolver: Optional[Any] = None,
    ) -> None:
        self.health_store = health_store or ProviderHealthStore()
        self.transport_resolver = transport_resolver

    def execute_plan(
        self,
        plan: RoutePlan,
        request: ExecutionRequest,
        budget: AttemptBudget,
    ) -> ExecutionResult:
        """Execute candidates in plan.eligible until one succeeds or all fail."""
        ...
```

Algorithm steps:
1. Verify `plan.eligible` is non-empty; raise `NoEligibleProviderError` if empty.
2. Initialize `attempts: list[TransportAttemptResult] = []`.
3. For each candidate in `plan.eligible`:
   a. Check `budget.remaining_seconds()`; if exhausted, break / raise `RequestDeadlineExceededError`.
   b. Compute attempt timeout via `budget.timeout_for_attempt(configured_timeout=..., future_attempts=remaining_count)`.
   c. Build `TransportRequest(candidate=candidate, messages=request.messages, timeout_seconds=attempt_timeout, ...)`.
   d. Call `execute_transport_attempt(transport_request, health_store=self.health_store)`.
   e. Record attempt in `attempts`.
   f. If `attempt.ok`: return `ExecutionResult(...)`.
   g. If `not attempt.error.fallback_eligible`: raise error immediately (terminal failure).
   h. Continue loop to next candidate.
4. If loop finishes without success: raise `AllCandidatesExhaustedError(attempts=tuple(attempts))`.

---

## 6. Executor Facade API

```python
def execute_chat(
    messages: Sequence[Mapping[str, str]],
    *,
    candidates: Optional[Sequence[RouteCandidate]] = None,
    data_class: DataClass = DataClass.INTERNAL_DATA,
    outbound_form: OutboundForm = OutboundForm.RAW,
    total_timeout_seconds: float = 30.0,
    temperature: float = 0.7,
    request_egress_authorized: bool = False,
    health_store: Optional[ProviderHealthStore] = None,
    policy: Optional[RoutePolicy] = None,
) -> ExecutionResult:
    """One-call high-level chat execution with automatic routing and fallback."""
    ...

def execute_prompt(
    prompt: str,
    *,
    system_prompt: str = "",
    **kwargs,
) -> ExecutionResult:
    """Convenience wrapper converting prompt string to standard chat messages."""
    ...
```

---

## 7. Implementation & Governance Roadmap

1. **Gate**: Platform-Control RFC & Governance Gate PR to authorize `S3_runtime_and_executor` work package.
2. **Phase 1 (Errors & Contracts)**: Add `AllCandidatesExhaustedError` to `ai_core.errors`, define dataclasses in `ai_core.runtime`.
3. **Phase 2 (Runtime Engine)**: Implement `SingleLoopRuntime` in `src/ai_core/runtime.py` with test suite `tests/test_s3_runtime.py`.
4. **Phase 3 (Executor Facade)**: Implement `execute_chat` and `execute_prompt` in `src/ai_core/executor.py` with test suite `tests/test_s3_executor.py`.
5. **Phase 4 (Root API Integration & Tag v0.3.0)**: Export top-level symbols, verify 100% backward compatibility, authorize and create tag `v0.3.0`.
