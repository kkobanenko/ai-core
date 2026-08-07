"""Классы данных и формы исходящего трафика для privacy-aware маршрутизации."""

from __future__ import annotations

from enum import Enum

from ai_core.provider_catalog import (
    NetworkBoundary,
    PiiPolicy,
    ProviderProfile,
)


class DataClass(str, Enum):
    """Классификация полезной нагрузки по чувствительности."""

    SYNTHETIC = "synthetic"
    PUBLIC_NO_PII = "public_no_pii"
    PUBLIC_POSSIBLE_PII = "public_possible_pii"
    PRIVATE_CLIENT_DATA = "private_client_data"
    SECRET = "secret"


class OutboundForm(str, Enum):
    """В каком виде данные уходят к провайдеру."""

    RAW = "raw"
    SANITIZED = "sanitized"
    SURROGATED = "surrogated"


# Классы, которые считаем чувствительными (raw наружу только при явной политике).
_SENSITIVE_DATA_CLASSES = frozenset(
    {
        DataClass.PUBLIC_POSSIBLE_PII,
        DataClass.PRIVATE_CLIENT_DATA,
        DataClass.SECRET,
    }
)


def is_sensitive_data_class(data_class: DataClass) -> bool:
    """True, если класс требует осторожного outbound (не SYNTHETIC / PUBLIC_NO_PII)."""
    return data_class in _SENSITIVE_DATA_CLASSES


def requires_raw_pii_allow(data_class: DataClass, outbound_form: OutboundForm) -> bool:
    """True, если маршруту нужен raw_pii_policy=ALLOW у провайдера."""
    if outbound_form != OutboundForm.RAW:
        return False
    return is_sensitive_data_class(data_class)


def provider_allows_raw_pii(profile: ProviderProfile) -> bool:
    """Проверить, разрешает ли профиль raw PII."""
    return profile.raw_pii_policy == PiiPolicy.ALLOW


def provider_allows_sanitized_pii(profile: ProviderProfile) -> bool:
    """Проверить, разрешает ли профиль sanitized/surrogated PII."""
    return profile.sanitized_pii_policy == PiiPolicy.ALLOW


def is_external_cloud(profile: ProviderProfile) -> bool:
    """Провайдер во внешнем облаке."""
    return profile.network_boundary == NetworkBoundary.EXTERNAL_CLOUD


def is_eligible_for_outbound(
    profile: ProviderProfile,
    data_class: DataClass,
    outbound_form: OutboundForm,
) -> bool:
    """Базовая eligibility без учёта health (только privacy + boundary).

    Правила:
    - SECRET в RAW никогда не уходит (даже на local).
    - SYNTHETIC: любой провайдер с допустимой политикой для формы.
    - RAW + sensitive: только raw_pii_policy=ALLOW (обычно local).
    - SANITIZED/SURROGATED: нужен sanitized_pii_policy=ALLOW;
      EXTERNAL_CLOUD при этом допустим.
    """
    # Секреты в сыром виде не отправляем никуда через этот слой.
    if data_class == DataClass.SECRET and outbound_form == OutboundForm.RAW:
        return False

    if data_class == DataClass.SYNTHETIC:
        # Синтетика безопасна: достаточно, что провайдер принимает текст.
        return profile.supports_text

    if outbound_form == OutboundForm.RAW:
        if requires_raw_pii_allow(data_class, outbound_form):
            return provider_allows_raw_pii(profile)
        # PUBLIC_NO_PII в RAW — ок при supports_text.
        return profile.supports_text

    # SANITIZED / SURROGATED
    if outbound_form in (OutboundForm.SANITIZED, OutboundForm.SURROGATED):
        if is_sensitive_data_class(data_class) or data_class == DataClass.PUBLIC_NO_PII:
            return provider_allows_sanitized_pii(profile)
        return profile.supports_text

    return False
