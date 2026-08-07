"""Privacy routing: raw не уходит в cloud; sanitized может; exhausted не leak."""

import pytest

from ai_core.health import ProviderHealthStatus, ProviderHealthStore
from ai_core.privacy import DataClass, OutboundForm
from ai_core.provider_catalog import NetworkBoundary, get_provider_profile
from ai_core.routing import PrivacyAwareRouter, RawRouteExhaustedError


def test_raw_sensitive_cannot_select_external_cloud():
    store = ProviderHealthStore()
    for pid in (
        "vm100_local_ollama",
        "ollama_cloud",
        "gpu_ollama",
        "mistral_external",
    ):
        store.set_status(pid, ProviderHealthStatus.REACHABLE)

    router = PrivacyAwareRouter(health_store=store)
    selected = router.select_eligible_providers(
        DataClass.PRIVATE_CLIENT_DATA,
        OutboundForm.RAW,
    )
    assert "vm100_local_ollama" in selected
    assert "ollama_cloud" not in selected
    assert "mistral_external" not in selected
    for pid in selected:
        assert get_provider_profile(pid).network_boundary != NetworkBoundary.EXTERNAL_CLOUD


def test_sanitized_sensitive_can_select_external():
    store = ProviderHealthStore()
    for pid in ("vm100_local_ollama", "ollama_cloud", "mistral_external"):
        store.set_status(pid, ProviderHealthStatus.REACHABLE)

    router = PrivacyAwareRouter(health_store=store)
    selected = router.select_eligible_providers(
        DataClass.PRIVATE_CLIENT_DATA,
        OutboundForm.SANITIZED,
    )
    assert "ollama_cloud" in selected or "mistral_external" in selected


def test_raw_exhausted_does_not_leak_raw_to_cloud():
    """Если local raw недоступен — ошибка, а не fallback на cloud."""
    store = ProviderHealthStore()
    store.set_status("vm100_local_ollama", ProviderHealthStatus.UNREACHABLE)
    store.set_status("ollama_cloud", ProviderHealthStatus.REACHABLE)
    store.set_status("mistral_external", ProviderHealthStatus.REACHABLE)
    store.set_status("gpu_ollama", ProviderHealthStatus.REACHABLE)

    router = PrivacyAwareRouter(health_store=store)
    with pytest.raises(RawRouteExhaustedError) as exc_info:
        router.select_or_raise_raw(DataClass.PRIVATE_CLIENT_DATA, OutboundForm.RAW)

    message = str(exc_info.value).lower()
    assert "sanitized" in message or "surrogated" in message or "transform" in message

    # Даже обычный select не должен вернуть external для raw sensitive
    selected = router.select_eligible_providers(
        DataClass.PRIVATE_CLIENT_DATA,
        OutboundForm.RAW,
    )
    assert selected == []
    assert "ollama_cloud" not in selected


def test_synthetic_allows_all_healthy_authorized():
    store = ProviderHealthStore()
    for pid in (
        "vm100_local_ollama",
        "ollama_cloud",
        "gpu_ollama",
        "mistral_external",
    ):
        store.set_status(pid, ProviderHealthStatus.REACHABLE)

    router = PrivacyAwareRouter(health_store=store)
    selected = router.select_eligible_providers(DataClass.SYNTHETIC, OutboundForm.RAW)
    assert set(selected) == {
        "vm100_local_ollama",
        "ollama_cloud",
        "gpu_ollama",
        "mistral_external",
    }


def test_quota_on_cloud_still_allows_local_raw():
    store = ProviderHealthStore()
    store.set_status("vm100_local_ollama", ProviderHealthStatus.REACHABLE)
    store.set_status("ollama_cloud", ProviderHealthStatus.QUOTA_LIMITED)

    router = PrivacyAwareRouter(health_store=store)
    selected = router.select_or_raise_raw(
        DataClass.PRIVATE_CLIENT_DATA,
        OutboundForm.RAW,
    )
    assert selected == ["vm100_local_ollama"]
