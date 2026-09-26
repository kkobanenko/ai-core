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
    fallback. LOCAL_SAME_HOST and INTERNAL_TRUSTED allow every valid
    non-SECRET class without request egress authorization. EXTERNAL and
    UNKNOWN_BOUNDARY still require literal request_egress_authorized=True.
    ``outbound_form`` is intentionally not used to weaken classification.
    """

    if not isinstance(data_class, DataClass):
        return False
    if not isinstance(outbound_form, OutboundForm):
        return False
    if not isinstance(network_boundary, NetworkBoundary):
        return False

    # SECRET запрещён на любой границе и в любой форме исходящих данных.
    if data_class is DataClass.SECRET:
        return False

    # Тот же хост: любой допустимый не-SECRET класс без разрешения на egress.
    if network_boundary is NetworkBoundary.LOCAL_SAME_HOST:
        return True

    # Внутренняя доверенная граница (gpu_ollama). Это не LOCAL_SAME_HOST.
    # Внешнее облачное разрешение на egress здесь не требуется.
    # SANITIZED и SURROGATED не понижают класс данных: класс уже проверен выше.
    if network_boundary is NetworkBoundary.INTERNAL_TRUSTED:
        return True

    # EXTERNAL и UNKNOWN_BOUNDARY: только буквальное True.
    return request_egress_authorized is True


__all__ = [
    "DataClass",
    "OutboundForm",
    "is_egress_eligible",
]
