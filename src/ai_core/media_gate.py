"""Проверка privacy + model capability перед media-вызовом (без исполнения fallback)."""

from __future__ import annotations

from ai_core.capabilities import ProviderCapability, require_model_capability
from ai_core.privacy import DataClass, OutboundForm, is_eligible_for_outbound
from ai_core.provider_catalog import get_provider_profile


class MediaPrivacyError(RuntimeError):
    """Запрос отклонён privacy-политикой (не fallback, а отказ)."""

    def __init__(self, message: str) -> None:
        self.category = "privacy_denied"
        super().__init__(message)


def assert_media_allowed(
    *,
    provider_id: str,
    model: str,
    capability: ProviderCapability,
    data_class: DataClass,
    outbound_form: OutboundForm,
) -> None:
    """Capability И privacy должны пройти. Router не вызывается как executor."""
    require_model_capability(provider_id, model, capability)
    profile = get_provider_profile(provider_id)
    if not is_eligible_for_outbound(profile, data_class, outbound_form):
        raise MediaPrivacyError(
            f"Provider {provider_id!r} not eligible for "
            f"data_class={data_class.value} outbound_form={outbound_form.value}"
        )
