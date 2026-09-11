"""Pure, fail-closed privacy and request-egress contracts."""

from __future__ import annotations

from enum import Enum

from ai_core.provider_catalog import NetworkBoundary


class DataClass(str, Enum):
    """Upstream payload classification supplied before route planning."""

    SYNTHETIC = "synthetic"
    PUBLIC_NO_PII = "public_no_pii"
    PUBLIC_POSSIBLE_PII = "public_possible_pii"
    PRIVATE_CLIENT_DATA = "private_client_data"
    SECRET = "secret"


class OutboundForm(str, Enum):
    """Payload form; transformation does not change its data classification."""

    RAW = "raw"
    SANITIZED = "sanitized"
    SURROGATED = "surrogated"


def is_egress_eligible(
    *,
    data_class: DataClass,
    outbound_form: OutboundForm,
    network_boundary: NetworkBoundary,
    request_egress_authorized: bool = False,
) -> bool:
    """Evaluate the pre-routing privacy and request-egress boundary.

    SECRET is denied before any transformation, lookup, routing, retry, or
    fallback. Non-local egress requires explicit request-level authorization.
    ``outbound_form`` is intentionally not used to weaken classification.
    """

    if data_class is DataClass.SECRET:
        return False

    if network_boundary is NetworkBoundary.LOCAL_SAME_HOST:
        return True

    return request_egress_authorized


__all__ = [
    "DataClass",
    "OutboundForm",
    "is_egress_eligible",
]
