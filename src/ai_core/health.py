"""Dependency-light provider/model health state.

Network probes belong to optional transport layers. This module only owns the
isolated state used by routing decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProviderHealthStatus(str, Enum):
    REACHABLE = "reachable"
    UNREACHABLE = "unreachable"
    QUOTA_LIMITED = "quota_limited"
    AUTH_FAILED = "auth_failed"
    MODEL_MISSING = "model_missing"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


_UNHEALTHY = frozenset(
    {
        ProviderHealthStatus.UNREACHABLE,
        ProviderHealthStatus.QUOTA_LIMITED,
        ProviderHealthStatus.AUTH_FAILED,
        ProviderHealthStatus.MODEL_MISSING,
        ProviderHealthStatus.TIMEOUT,
    }
)


@dataclass(frozen=True)
class HealthTarget:
    provider_id: str
    model: str | None = None


@dataclass
class ProviderHealthStore:
    """Health is isolated by provider identity and optionally by model.

    Unknown means "not observed yet" and does not block a route. An explicitly
    unhealthy provider blocks all its models; a model-specific failure blocks
    only that model.
    """

    _status: dict[HealthTarget, ProviderHealthStatus] = field(default_factory=dict)

    def set_status(
        self,
        provider_id: str,
        status: ProviderHealthStatus,
        *,
        model: str | None = None,
    ) -> None:
        self._status[HealthTarget(provider_id=provider_id, model=model)] = status

    def get_status(self, provider_id: str, *, model: str | None = None) -> ProviderHealthStatus:
        return self._status.get(
            HealthTarget(provider_id=provider_id, model=model),
            ProviderHealthStatus.UNKNOWN,
        )

    def is_healthy(self, provider_id: str, *, model: str | None = None) -> bool:
        provider_status = self.get_status(provider_id)
        if provider_status in _UNHEALTHY:
            return False
        if model is None:
            return provider_status in (ProviderHealthStatus.UNKNOWN, ProviderHealthStatus.REACHABLE)
        model_status = self.get_status(provider_id, model=model)
        return model_status in (ProviderHealthStatus.UNKNOWN, ProviderHealthStatus.REACHABLE)

    def is_unhealthy(self, provider_id: str, *, model: str | None = None) -> bool:
        return not self.is_healthy(provider_id, model=model)

    def clear(self, provider_id: str, *, model: str | None = None) -> None:
        self._status.pop(HealthTarget(provider_id=provider_id, model=model), None)

    def snapshot(self) -> dict[str, str]:
        """Metadata-only health snapshot suitable for diagnostics/tracing."""

        result: dict[str, str] = {}
        for target, status in self._status.items():
            key = target.provider_id if target.model is None else f"{target.provider_id}/{target.model}"
            result[key] = status.value
        return result
