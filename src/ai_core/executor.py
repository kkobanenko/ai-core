"""S3 High-Level Developer Ergonomics: Executor Facade.

Provides one-call chat and prompt execution functions (`execute_chat`, `execute_prompt`)
that encapsulate planning, privacy egress checks, health observation, time budgeting,
and deterministic fallback into a simple, production-ready interface.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ai_core.capabilities import ProviderCapability
from ai_core.health import ProviderHealthStore
from ai_core.privacy import DataClass, OutboundForm
from ai_core.provider_catalog import CANONICAL_PROVIDER_IDS
from ai_core.routing import (
    CapabilityAuthorization,
    PrivacyAwareRouter,
    RouteCandidate,
    RoutePolicy,
)
from ai_core.runtime import (
    ExecutionRequest,
    ExecutionResult,
    SingleLoopRuntime,
)
from ai_core.transports import ProviderTransport

DEFAULT_CANDIDATES: tuple[RouteCandidate, ...] = (
    RouteCandidate(provider_id="vm100_local_ollama", model="qwen3:8b"),
    RouteCandidate(provider_id="gpu_ollama", model="qwen3:8b"),
    RouteCandidate(provider_id="mistral_external", model="mistral-small-latest"),
)

DEFAULT_GOVERNED_MODELS: frozenset[tuple[str, str]] = frozenset(
    (c.provider_id, c.model) for c in DEFAULT_CANDIDATES
)


def _build_default_policy(
    candidates: tuple[RouteCandidate, ...],
    capability: ProviderCapability,
    request_egress_authorized: bool,
) -> RoutePolicy:
    """Construct a RoutePolicy authorizing strictly default governed provider-model pairs."""
    authorized_pairs = tuple(
        c for c in candidates if (c.provider_id, c.model) in DEFAULT_GOVERNED_MODELS
    )
    authorized_providers = frozenset(c.provider_id for c in authorized_pairs)
    capability_auths = frozenset(
        CapabilityAuthorization(
            provider_id=c.provider_id,
            model=c.model,
            capability=capability,
        )
        for c in authorized_pairs
    )
    return RoutePolicy(
        authorized_provider_ids=authorized_providers,
        capability_authorizations=capability_auths,
        request_egress_authorized=request_egress_authorized,
    )


def execute_chat(
    messages: Sequence[Mapping[str, str]],
    *,
    candidates: Sequence[RouteCandidate] | None = None,
    capability: ProviderCapability = ProviderCapability.TEXT,
    data_class: DataClass = DataClass.PUBLIC_NO_PII,
    outbound_form: OutboundForm = OutboundForm.RAW,
    total_timeout_seconds: float = 30.0,
    temperature: float = 0.7,
    request_egress_authorized: bool = False,
    health_store: ProviderHealthStore | None = None,
    policy: RoutePolicy | None = None,
    runtime: SingleLoopRuntime | None = None,
    transport: ProviderTransport | None = None,
    extra_options: Mapping[str, Any] | None = None,
) -> ExecutionResult:
    """Execute a chat completion request with deterministic planning and single-loop fallback.

    Args:
        messages: Sequence of message mappings with 'role' and 'content'.
        candidates: Optional custom sequence of RouteCandidates to consider in priority order.
        capability: Required capability (default: ProviderCapability.CHAT).
        data_class: Privacy classification of payload (default: INTERNAL_DATA).
        outbound_form: Outbound representation (default: RAW).
        total_timeout_seconds: Total deadline for all attempts combined (default: 30.0s).
        temperature: Sampling temperature (default: 0.7).
        request_egress_authorized: Explicit user consent for external network egress.
        health_store: Shared provider health store for circuit observations.
        policy: Optional custom routing policy; if omitted, standard policy is derived.
        runtime: Optional custom SingleLoopRuntime instance.
        transport: Optional custom ProviderTransport (useful for mock testing).
        extra_options: Optional provider-specific pass-through arguments.

    Returns:
        ExecutionResult containing response, winning candidate, attempts history, and total latency.

    Raises:
        NoEligibleProviderError: If router rejects all candidates before execution.
        AllCandidatesExhaustedError: If all eligible candidates failed during execution.
        RequestDeadlineExceededError: If shared time budget expires.
    """
    resolved_candidates = (
        tuple(candidates) if candidates is not None else DEFAULT_CANDIDATES
    )
    resolved_health_store = (
        health_store
        or (runtime.health_store if runtime is not None else None)
        or ProviderHealthStore()
    )
    resolved_policy = policy or _build_default_policy(
        candidates=resolved_candidates,
        capability=capability,
        request_egress_authorized=request_egress_authorized,
    )

    router = PrivacyAwareRouter(health_store=resolved_health_store)
    plan = router.plan(
        resolved_candidates,
        capability=capability,
        data_class=data_class,
        outbound_form=outbound_form,
        policy=resolved_policy,
        require_nonempty=True,
    )

    request = ExecutionRequest(
        messages=tuple(dict(m) for m in messages),
        candidates=resolved_candidates,
        capability=capability,
        data_class=data_class,
        outbound_form=outbound_form,
        total_timeout_seconds=total_timeout_seconds,
        temperature=temperature,
        extra_options=extra_options or {},
        request_egress_authorized=request_egress_authorized,
    )

    exec_runtime = runtime or SingleLoopRuntime(
        health_store=resolved_health_store,
        transport=transport,
    )
    return exec_runtime.execute_plan(
        plan=plan,
        request=request,
        transport=transport,
    )


def execute_prompt(
    prompt: str,
    *,
    system_prompt: str = "",
    **kwargs: Any,
) -> ExecutionResult:
    """Convenience facade: converts prompt string and optional system_prompt to chat messages."""
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return execute_chat(messages, **kwargs)


__all__ = [
    "DEFAULT_CANDIDATES",
    "execute_chat",
    "execute_prompt",
]
