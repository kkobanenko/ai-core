"""Health isolation: quota на ollama_cloud не роняет vm100/gpu."""

from ai_core.health import (
    ProviderHealthStatus,
    ProviderHealthStore,
    mark_quota_limited,
)


def test_quota_on_ollama_cloud_does_not_affect_others():
    store = ProviderHealthStore()
    store.set_status("vm100_local_ollama", ProviderHealthStatus.REACHABLE)
    store.set_status("gpu_ollama", ProviderHealthStatus.REACHABLE)
    store.set_status("ollama_cloud", ProviderHealthStatus.REACHABLE)

    mark_quota_limited(store, "ollama_cloud")

    assert store.get_status("ollama_cloud") == ProviderHealthStatus.QUOTA_LIMITED
    assert store.is_unhealthy("ollama_cloud")
    assert store.get_status("vm100_local_ollama") == ProviderHealthStatus.REACHABLE
    assert store.get_status("gpu_ollama") == ProviderHealthStatus.REACHABLE
    assert store.is_healthy("vm100_local_ollama")
    assert store.is_healthy("gpu_ollama")


def test_unknown_status_is_treated_as_selectable():
    store = ProviderHealthStore()
    assert store.get_status("mistral_external") == ProviderHealthStatus.UNKNOWN
    assert store.is_healthy("mistral_external")
