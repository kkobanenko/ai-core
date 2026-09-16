"""Dependency-light observational provider/model health state."""

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


_BLOCKING_STATUSES = frozenset(
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
    """Store observations; health never grants routing authorization."""

    _status: dict[
        HealthTarget,
        ProviderHealthStatus,
    ] = field(default_factory=dict)

    def set_status(
        self,
        provider_id: str,
        status: ProviderHealthStatus,
        *,
        model: str | None = None,
    ) -> None:
        if not isinstance(status, ProviderHealthStatus):
            raise ValueError(
                "status must be ProviderHealthStatus"
            )

        self._status[
            HealthTarget(
                provider_id=provider_id,
                model=model,
            )
        ] = status

    def get_status(
        self,
        provider_id: str,
        *,
        model: str | None = None,
    ) -> ProviderHealthStatus:
        return self._status.get(
            HealthTarget(
                provider_id=provider_id,
                model=model,
            ),
            ProviderHealthStatus.UNKNOWN,
        )

    def blocks_route(
        self,
        provider_id: str,
        *,
        model: str | None = None,
    ) -> bool:
        provider_status = self.get_status(provider_id)

        if provider_status in _BLOCKING_STATUSES:
            return True

        if model is None:
            return False

        model_status = self.get_status(
            provider_id,
            model=model,
        )

        return model_status in _BLOCKING_STATUSES

    def clear(
        self,
        provider_id: str,
        *,
        model: str | None = None,
    ) -> None:
        self._status.pop(
            HealthTarget(
                provider_id=provider_id,
                model=model,
            ),
            None,
        )

    def snapshot(self) -> dict[str, str]:
        result: dict[str, str] = {}

        for target, status in self._status.items():
            key = (
                target.provider_id
                if target.model is None
                else f"{target.provider_id}/{target.model}"
            )
            result[key] = status.value

        return result


__all__ = [
    "HealthTarget",
    "ProviderHealthStatus",
    "ProviderHealthStore",
]
