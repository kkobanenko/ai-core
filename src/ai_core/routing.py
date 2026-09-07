"""Deterministic capability/privacy/health route planning.

This module plans eligible candidates only. It does not execute provider calls,
retry them, sanitize payloads, or own workflow orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ai_core.capabilities import ProviderCapability, model_has_capability
from ai_core.errors import NoEligibleProviderError, RawRouteExhaustedError
from ai_core.health import ProviderHealthStore
from ai_core.privacy import DataClass, OutboundForm, is_eligible_for_outbound, requires_raw_pii_allow
from ai_core.provider_catalog import get_provider_catalog, get_provider_profile


@dataclass(frozen=True)
class RouteCandidate:
    provider_id: str
    model: str


class RejectionReason(str, Enum):
    UNKNOWN_PROVIDER = "unknown_provider"
    UNAUTHORIZED_PROVIDER = "unauthorized_provider"
    PRIVACY_POLICY = "privacy_policy"
    CAPABILITY = "capability"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class RejectedCandidate:
    candidate: RouteCandidate
    reason: RejectionReason


@dataclass(frozen=True)
class RoutePlan:
    eligible: tuple[RouteCandidate, ...]
    rejected: tuple[RejectedCandidate, ...]

    @property
    def winner(self) -> RouteCandidate | None:
        return self.eligible[0] if self.eligible else None


@dataclass
class PrivacyAwareRouter:
    """Build deterministic eligible order without executing fallback.

    The caller remains responsible for using one fallback owner. Candidate order
    is deterministic: provider priority, provider id, then model id.
    """

    health_store: ProviderHealthStore = field(default_factory=ProviderHealthStore)
    authorized_provider_ids: tuple[str, ...] | None = None

    def _authorized_ids(self) -> set[str]:
        catalog = get_provider_catalog()
        if self.authorized_provider_ids is None:
            return set(catalog)
        return {provider_id for provider_id in self.authorized_provider_ids if provider_id in catalog}

    def plan(
        self,
        candidates: tuple[RouteCandidate, ...] | list[RouteCandidate],
        *,
        capability: ProviderCapability,
        data_class: DataClass,
        outbound_form: OutboundForm,
        require_nonempty: bool = False,
    ) -> RoutePlan:
        catalog = get_provider_catalog()
        authorized = self._authorized_ids()
        accepted: list[tuple[int, str, str, RouteCandidate]] = []
        rejected: list[RejectedCandidate] = []

        for candidate in candidates:
            if candidate.provider_id not in catalog:
                rejected.append(RejectedCandidate(candidate, RejectionReason.UNKNOWN_PROVIDER))
                continue
            if candidate.provider_id not in authorized:
                rejected.append(RejectedCandidate(candidate, RejectionReason.UNAUTHORIZED_PROVIDER))
                continue

            profile = get_provider_profile(candidate.provider_id)
            if not is_eligible_for_outbound(profile, data_class, outbound_form):
                rejected.append(RejectedCandidate(candidate, RejectionReason.PRIVACY_POLICY))
                continue
            if not model_has_capability(candidate.provider_id, candidate.model, capability):
                rejected.append(RejectedCandidate(candidate, RejectionReason.CAPABILITY))
                continue
            if not self.health_store.is_healthy(candidate.provider_id, model=candidate.model):
                rejected.append(RejectedCandidate(candidate, RejectionReason.UNHEALTHY))
                continue

            accepted.append(
                (profile.priority_hint, candidate.provider_id, candidate.model, candidate)
            )

        accepted.sort(key=lambda item: (item[0], item[1], item[2]))
        plan = RoutePlan(
            eligible=tuple(item[3] for item in accepted),
            rejected=tuple(rejected),
        )

        if not plan.eligible:
            if (
                outbound_form == OutboundForm.RAW
                and requires_raw_pii_allow(data_class, outbound_form)
            ):
                raise RawRouteExhaustedError()
            if require_nonempty:
                raise NoEligibleProviderError(
                    f"No eligible provider for capability={capability.value}, "
                    f"data_class={data_class.value}, outbound_form={outbound_form.value}"
                )
        return plan
