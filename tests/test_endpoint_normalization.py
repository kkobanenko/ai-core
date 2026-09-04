"""AU02A: endpoint URL normalization via ProviderProfile metadata (no live network)."""

from __future__ import annotations

import inspect

import pytest

from ai_core.provider_catalog import (
    PROVIDER_GPU_OLLAMA,
    PROVIDER_MISTRAL_EXTERNAL,
    PROVIDER_OLLAMA_CLOUD,
    PROVIDER_VM100_LOCAL_OLLAMA,
    get_provider_profile,
)
from ai_core.resolve import normalize_endpoint_base_url, resolve_provider_endpoint
import ai_core.resolve as resolve_mod


def test_gpu_bare_host_gets_http_and_default_port(monkeypatch):
    monkeypatch.setenv("LOCAL_GPU_OLLAMA_HOST", "gpu.internal")
    monkeypatch.delenv("LOCAL_GPU_OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("LOCAL_GPU_OLLAMA_URL", raising=False)
    ep = resolve_provider_endpoint(PROVIDER_GPU_OLLAMA)
    assert ep.base_url == "http://gpu.internal:11434"


def test_gpu_host_with_explicit_port(monkeypatch):
    monkeypatch.setenv("LOCAL_GPU_OLLAMA_HOST", "gpu.internal:12000")
    monkeypatch.delenv("LOCAL_GPU_OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("LOCAL_GPU_OLLAMA_URL", raising=False)
    ep = resolve_provider_endpoint(PROVIDER_GPU_OLLAMA)
    assert ep.base_url == "http://gpu.internal:12000"


def test_gpu_full_url_unchanged(monkeypatch):
    monkeypatch.setenv("LOCAL_GPU_OLLAMA_HOST", "http://gpu.internal:11434")
    monkeypatch.delenv("LOCAL_GPU_OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("LOCAL_GPU_OLLAMA_URL", raising=False)
    ep = resolve_provider_endpoint(PROVIDER_GPU_OLLAMA)
    assert ep.base_url == "http://gpu.internal:11434"


def test_gpu_base_url_env_unchanged(monkeypatch):
    monkeypatch.delenv("LOCAL_GPU_OLLAMA_HOST", raising=False)
    monkeypatch.setenv("LOCAL_GPU_OLLAMA_BASE_URL", "http://gpu2.internal:11434")
    monkeypatch.delenv("LOCAL_GPU_OLLAMA_URL", raising=False)
    ep = resolve_provider_endpoint(PROVIDER_GPU_OLLAMA)
    assert ep.base_url == "http://gpu2.internal:11434"


def test_ollama_cloud_bare_host_https_no_default_port():
    assert (
        normalize_endpoint_base_url(
            "ollama.com",
            default_scheme="https",
            default_port=None,
        )
        == "https://ollama.com"
    )


def test_endpoint_metadata_configured_intentionally():
    vm = get_provider_profile(PROVIDER_VM100_LOCAL_OLLAMA)
    assert vm.endpoint_default_scheme == "http"
    assert vm.endpoint_default_port == 11434
    gpu = get_provider_profile(PROVIDER_GPU_OLLAMA)
    assert gpu.endpoint_default_scheme == "http"
    assert gpu.endpoint_default_port == 11434
    cloud = get_provider_profile(PROVIDER_OLLAMA_CLOUD)
    assert cloud.endpoint_default_scheme == "https"
    assert cloud.endpoint_default_port is None
    mistral = get_provider_profile(PROVIDER_MISTRAL_EXTERNAL)
    assert mistral.endpoint_default_scheme == "https"
    assert mistral.endpoint_default_port is None


def test_resolver_has_no_provider_id_name_heuristics():
    src = inspect.getsource(resolve_mod)
    assert 'endswith("ollama")' not in src
    assert "provider_id.endswith" not in src
    assert 'provider_id == "gpu_ollama"' not in src
    assert "if provider_id ==" not in src
