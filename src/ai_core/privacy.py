"""Fail-closed privacy eligibility for provider routing."""

from __future__ import annotations

from enum import Enum

from ai_core.provider_catalog import NetworkBoundary, PiiPolicy, ProviderProfile


class DataClass(str, Enum):
    SYNTHETIC = "synthetic"
    PUBLIC_NO_PII = "public_no_pii"
    PUBLIC_POSSIBLE_PII = "public_possible_pii"
    PRIVATE_CLIENT_DATA = "private_client_data"
    SECRET = "secret"


class OutboundForm(str, Enum):
    RAW = "raw"
    SANITIZED = "sanitized"
    SURROGATED = "surrogated"


_SENSITIVE_DATA_CLASSES = frozenset(
    {
        DataClass.PUBLIC_POSSIBLE_PII,
        DataClass.PRIVATE_CLIENT_DATA,
        DataClass.SECRET,
    }
)


def is_sensitive_data_class(data_class: DataClass) -> bool:
    return data_class in _SENSITIVE_DATA_CLASSES


def requires_raw_pii_allow(data_class: DataClass, outbound_form: OutboundForm) -> bool:
    return outbound_form == OutboundForm.RAW and is_sensitive_data_class(data_class)


def provider_allows_raw_pii(profile: ProviderProfile) -> bool:
    return profile.raw_pii_policy == PiiPolicy.ALLOW


def provider_allows_sanitized_pii(profile: ProviderProfile) -> bool:
    return profile.sanitized_pii_policy == PiiPolicy.ALLOW


def is_external_cloud(profile: ProviderProfile) -> bool:
    return profile.network_boundary == NetworkBoundary.EXTERNAL_CLOUD


def is_eligible_for_outbound(
    profile: ProviderProfile,
    data_class: DataClass,
    outbound_form: OutboundForm,
) -> bool:
    """Return whether a provider may receive this payload form.

    Important invariant: SECRET+RAW is always blocked. Sensitive RAW is only
    eligible for providers explicitly marked raw_pii_policy=ALLOW. A caller
    must create a new SANITIZED/SURROGATED request before external fallback.
    """

    if data_class == DataClass.SECRET and outbound_form == OutboundForm.RAW:
        return False

    if data_class == DataClass.SYNTHETIC:
        return profile.supports_text

    if outbound_form == OutboundForm.RAW:
        if requires_raw_pii_allow(data_class, outbound_form):
            return provider_allows_raw_pii(profile)
        return profile.supports_text

    if outbound_form in (OutboundForm.SANITIZED, OutboundForm.SURROGATED):
        if is_sensitive_data_class(data_class) or data_class == DataClass.PUBLIC_NO_PII:
            return provider_allows_sanitized_pii(profile)
        return profile.supports_text

    return False
