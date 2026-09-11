import os
from pathlib import Path
import subprocess
import sys

import ai_core
from ai_core import capabilities, privacy, provider_catalog


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROOT_API = [
    "AttributeValue",
    "PhoenixConfig",
    "init_tracing",
    "load_phoenix_config",
    "maybe_truncate",
    "record_llm_result",
    "sanitize_attributes",
    "shutdown_tracing",
    "start_llm_span",
]


def test_root_api_remains_the_exact_nine_symbol_contract() -> None:
    assert ai_core.__all__ == EXPECTED_ROOT_API
    assert not set(ai_core.__all__) & {
        *provider_catalog.__all__,
        *capabilities.__all__,
        *privacy.__all__,
    }


def test_tracing_import_does_not_load_foundation_or_provider_dependencies() -> None:
    code = """
import sys
import ai_core.tracing

assert 'ai_core.provider_catalog' not in sys.modules
assert 'ai_core.capabilities' not in sys.modules
assert 'ai_core.privacy' not in sys.modules
assert 'httpx' not in sys.modules
assert 'langchain' not in sys.modules
assert 'openai' not in sys.modules
assert 'mistralai' not in sys.modules
assert 'ollama' not in sys.modules
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")

    subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_project_dependencies_do_not_expand_for_s1() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"arize-phoenix-otel==0.16.1"' in pyproject
    for forbidden_dependency in (
        '"httpx',
        '"langchain',
        '"openai',
        '"mistral',
        '"ollama',
    ):
        assert forbidden_dependency not in pyproject


def test_s1_surfaces_exclude_aliases_concrete_profiles_stt_and_new_ids() -> None:
    assert not hasattr(provider_catalog, "resolve_provider_id")
    assert not hasattr(provider_catalog, "PROVIDER_ALIASES")
    assert not hasattr(capabilities, "_MODEL_PROFILES")
    assert not hasattr(capabilities, "list_model_profiles")

    exported_names = {
        *provider_catalog.__all__,
        *capabilities.__all__,
        *privacy.__all__,
        *capabilities.ProviderCapability.__members__,
    }
    assert "STT_SEGMENTS" not in exported_names
    assert "gpu_whisper" not in provider_catalog.CANONICAL_PROVIDER_IDS
    assert "openai_external" not in provider_catalog.CANONICAL_PROVIDER_IDS
    assert "deepseek_external" not in provider_catalog.CANONICAL_PROVIDER_IDS
