"""Privacy-aware выбор eligible провайдеров (без авто-отправки raw во внешнее облако)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_core.health import ProviderHealthStore
from ai_core.privacy import (
    DataClass,
    OutboundForm,
    is_eligible_for_outbound,
    requires_raw_pii_allow,
)
from ai_core.provider_catalog import (
    get_provider_catalog,
    get_provider_profile,
)


class RawRouteExhaustedError(RuntimeError):
    """RAW-маршрут исчерпан: нет здорового провайдера с raw_pii_policy=ALLOW.

    Вызывающий должен создать НОВЫЙ запрос в SANITIZED/SURROGATED форме.
    Этот слой НЕ перенаправляет raw автоматически во EXTERNAL_CLOUD.
    """

    def __init__(self, message: str | None = None) -> None:
        default = (
            "Raw route exhausted: no healthy provider allows raw PII. "
            "Transform payload to sanitized/surrogated and create a NEW request. "
            "Do not auto-send raw sensitive data to external cloud."
        )
        super().__init__(message or default)


@dataclass
class PrivacyAwareRouter:
    """Выбирает eligible provider_id по data_class + outbound_form + health.

    Fallback ownership остаётся у LangChainJsonClient — но только внутри
    eligible-набора, который вернул этот роутер.
    """

    health_store: ProviderHealthStore = field(default_factory=ProviderHealthStore)
    # Опциональный whitelist; None = весь каталог.
    authorized_provider_ids: tuple[str, ...] | None = None

    def _authorized_ids(self) -> list[str]:
        catalog = get_provider_catalog()
        if self.authorized_provider_ids is None:
            return list(catalog.keys())
        return [pid for pid in self.authorized_provider_ids if pid in catalog]

    def select_eligible_providers(
        self,
        data_class: DataClass,
        outbound_form: OutboundForm,
    ) -> list[str]:
        """Вернуть список provider_id, отсортированный по priority_hint (asc).

        Учитывает privacy eligibility и per-provider health.
        Не поднимает исключение сам — для RAW смотри select_or_raise_raw.
        """
        eligible: list[tuple[int, str]] = []
        for provider_id in self._authorized_ids():
            profile = get_provider_profile(provider_id)
            if not is_eligible_for_outbound(profile, data_class, outbound_form):
                continue
            if not self.health_store.is_healthy(provider_id):
                continue
            eligible.append((profile.priority_hint, provider_id))

        eligible.sort(key=lambda item: (item[0], item[1]))
        return [provider_id for _, provider_id in eligible]

    def select_or_raise_raw(
        self,
        data_class: DataClass,
        outbound_form: OutboundForm = OutboundForm.RAW,
    ) -> list[str]:
        """Как select_eligible_providers, но для чувствительного RAW —
        при пустом наборе бросает RawRouteExhaustedError.
        """
        selected = self.select_eligible_providers(data_class, outbound_form)
        if (
            outbound_form == OutboundForm.RAW
            and requires_raw_pii_allow(data_class, outbound_form)
            and not selected
        ):
            raise RawRouteExhaustedError()
        return selected

    def assert_not_leaking_raw_to_external(
        self,
        provider_ids: list[str],
        data_class: DataClass,
        outbound_form: OutboundForm,
    ) -> None:
        """Защитный assert: sensitive RAW не должен включать EXTERNAL_CLOUD ids."""
        if outbound_form != OutboundForm.RAW:
            return
        if not requires_raw_pii_allow(data_class, outbound_form):
            return
        for provider_id in provider_ids:
            profile = get_provider_profile(provider_id)
            from ai_core.privacy import is_external_cloud

            if is_external_cloud(profile):
                raise RawRouteExhaustedError(
                    f"Refusing raw sensitive route to external provider: {provider_id}"
                )
