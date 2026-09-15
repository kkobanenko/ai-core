"""Deterministic bounded route planning over current S1 contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ai_core.capabilities import ProviderCapability
from ai_core.errors import NoEligibleProviderError
from ai_core.health import ProviderHealthStore
from ai_core.privacy import (
    DataClass,
    OutboundForm,
    is_egress_eligible,
)
from ai_core.provider_catalog import (
    UnknownProviderIdentityError,
    get_provider_identity,
)


@dataclass(frozen=True)
class RouteCandidate:
    provider_id: str
    model: str


@dataclass(frozen=True)
class CapabilityAuthorization:
    provider_id: str
    model: str
    capability: ProviderCapability


@dataclass(frozen=True)
class RoutePolicy:
    authorized_provider_ids: frozenset[str]
    capability_authorizations: frozenset[
        CapabilityAuthorization
    ]
    request_egress_authorized: object = False


class RejectionReason(str, Enum):
    UNKNOWN_PROVIDER = "unknown_provider"
    UNAUTHORIZED_PROVIDER = "unauthorized_provider"
    CAPABILITY_NOT_AUTHORIZED = (
        "capability_not_authorized"
    )
    PRIVACY_EGRESS_DENIED = "privacy_egress_denied"
    HEALTH_BLOCKED = "health_blocked"


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
        if not self.eligible:
            return None
        return self.eligible[0]


@dataclass
class PrivacyAwareRouter:
    """Filter candidates without executing retry or fallback."""

    health_store: ProviderHealthStore = field(
        default_factory=ProviderHealthStore
    )

    def plan(
        self,
        candidates: tuple[RouteCandidate, ...]
        | list[RouteCandidate],
        *,
        capability: ProviderCapability,
        data_class: DataClass,
        outbound_form: OutboundForm,
        policy: RoutePolicy,
        require_nonempty: bool = False,
    ) -> RoutePlan:
        eligible: list[RouteCandidate] = []
        rejected: list[RejectedCandidate] = []

        for candidate in candidates:
            try:
                identity = get_provider_identity(
                    candidate.provider_id
                )
            except UnknownProviderIdentityError:
                rejected.append(
                    RejectedCandidate(
                        candidate,
                        RejectionReason.UNKNOWN_PROVIDER,
                    )
                )
                continue

            if (
                candidate.provider_id
                not in policy.authorized_provider_ids
            ):
                rejected.append(
                    RejectedCandidate(
                        candidate,
                        RejectionReason.UNAUTHORIZED_PROVIDER,
                    )
                )
                continue

            required_authorization = (
                CapabilityAuthorization(
                    provider_id=candidate.provider_id,
                    model=candidate.model,
                    capability=capability,
                )
            )

            if (
                required_authorization
                not in policy.capability_authorizations
            ):
                rejected.append(
                    RejectedCandidate(
                        candidate,
                        RejectionReason.CAPABILITY_NOT_AUTHORIZED,
                    )
                )
                continue

            if not is_egress_eligible(
                data_class=data_class,
                outbound_form=outbound_form,
                network_boundary=identity.network_boundary,
                request_egress_authorized=(
                    policy.request_egress_authorized
                ),
            ):
                rejected.append(
                    RejectedCandidate(
                        candidate,
                        RejectionReason.PRIVACY_EGRESS_DENIED,
                    )
                )
                continue

            if self.health_store.blocks_route(
                candidate.provider_id,
                model=candidate.model,
            ):
                rejected.append(
                    RejectedCandidate(
                        candidate,
                        RejectionReason.HEALTH_BLOCKED,
                    )
                )
                continue

            eligible.append(candidate)

        plan = RoutePlan(
            eligible=tuple(eligible),
            rejected=tuple(rejected),
        )

        if require_nonempty and not plan.eligible:
            raise NoEligibleProviderError(
                "No candidate survived the explicit "
                "routing authorization, privacy, "
                "and health gates"
            )

        return plan


__all__ = [
    "CapabilityAuthorization",
    "PrivacyAwareRouter",
    "RejectedCandidate",
    "RejectionReason",
    "RouteCandidate",
    "RoutePlan",
    "RoutePolicy",
]
