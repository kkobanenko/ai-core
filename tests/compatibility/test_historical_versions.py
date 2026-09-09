from __future__ import annotations

import ast
import json
from pathlib import Path
import re

import pytest

from tests.compatibility.ast_contract import module_contract
from tests.compatibility.git_ref import list_paths, read_blob, resolve_tag


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "compatibility"
    / "historical_versions.v1.json"
)
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
VERSIONS = FIXTURE["versions"]
V02_DEPENDENCY_PREFIXES = (
    "langchain-",
    "httpx",
    "opentelemetry-",
)


def _dependencies(pyproject: str) -> list[str]:
    match = re.search(r"(?ms)^dependencies\s*=\s*(\[.*?^\])", pyproject)
    assert match is not None
    parsed = ast.literal_eval(match.group(1))
    assert isinstance(parsed, list)
    return parsed


def _canonical_provider_ids(source: str) -> list[str]:
    tree = ast.parse(source)
    strings: dict[str, str] = {}
    canonical_names: list[str] | None = None
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            strings[target.id] = node.value.value
        if target.id == "CANONICAL_PROVIDER_IDS" and isinstance(node.value, ast.Tuple):
            canonical_names = [
                item.id for item in node.value.elts if isinstance(item, ast.Name)
            ]
    assert canonical_names is not None
    return [strings[name] for name in canonical_names]


def test_fixture_is_versioned_observed_evidence_not_future_contract() -> None:
    assert FIXTURE["schema_version"] == 1
    assert FIXTURE["evidence_class"] == "OBSERVED_HISTORICAL_EVIDENCE"
    assert list(VERSIONS) == ["v0.1.0", "v0.2.0", "v0.2.1", "v0.2.2"]
    assert all(not item["normative_future_api"] for item in VERSIONS.values())


@pytest.mark.parametrize("tag", VERSIONS)
def test_version_fixture_matches_immutable_git_object(tag: str) -> None:
    expected = VERSIONS[tag]
    sha = expected["sha"]

    assert resolve_tag(tag) == sha
    assert list(list_paths(sha, "src/ai_core")) == expected["modules"]
    assert module_contract(read_blob(sha, "src/ai_core/__init__.py"))["exports"] == expected[
        "root_exports"
    ]
    pyproject = read_blob(sha, "pyproject.toml")
    assert f'version = "{tag.removeprefix("v")}"' in pyproject
    assert _dependencies(pyproject) == expected["dependencies"]


def test_v010_is_tracing_only_without_inference_dependency_family() -> None:
    release = VERSIONS["v0.1.0"]

    assert release["inference_apis"] == []
    assert release["capability_enum"] == []
    assert not any(
        dependency.startswith(V02_DEPENDENCY_PREFIXES)
        for dependency in release["dependencies"]
    )


def test_v020_introduces_json_client_and_hard_provider_dependencies() -> None:
    release = VERSIONS["v0.2.0"]
    contract = module_contract(read_blob(release["sha"], "src/ai_core/json_client.py"))
    method = contract["classes"]["LangChainJsonClient"]["methods"][
        "create_json_completion"
    ]

    assert release["inference_apis"] == [
        "LangChainJsonClient.create_json_completion"
    ]
    assert [item["name"] for item in method["positional"]] == [
        "self",
        "system_prompt",
        "user_prompt",
    ]
    assert {
        "langchain-core==1.4.9",
        "langchain-ollama==1.1.0",
        "langchain-mistralai==1.1.6",
        "langchain-openai==1.3.5",
        "httpx>=0.27,<1",
    }.issubset(release["dependencies"])


@pytest.mark.parametrize("tag", ["v0.2.0", "v0.2.1", "v0.2.2"])
def test_v02_model_record_shapes_are_stable(tag: str) -> None:
    release = VERSIONS[tag]
    classes = module_contract(read_blob(release["sha"], "src/ai_core/models.py"))[
        "classes"
    ]

    assert [field["name"] for field in classes["ProviderConfig"]["fields"]] == [
        "name",
        "transport",
        "model",
        "base_url",
        "api_key",
        "api_key_optional",
        "timeout_seconds",
        "headers",
    ]
    assert [field["name"] for field in classes["AttemptRecord"]["fields"]] == [
        "provider",
        "model",
        "attempt_index",
        "outcome",
        "reason",
        "latency_ms",
    ]
    assert [field["name"] for field in classes["JsonCompletion"]["fields"]] == [
        "raw_content",
        "provider_name",
        "model_name",
        "input_tokens",
        "output_tokens",
        "latency_ms",
        "attempt_summary",
    ]


@pytest.mark.parametrize("tag", ["v0.2.1", "v0.2.2"])
def test_v021_and_v022_observe_only_the_four_recorded_provider_ids(tag: str) -> None:
    release = VERSIONS[tag]
    source = read_blob(release["sha"], "src/ai_core/provider_catalog.py")

    assert _canonical_provider_ids(source) == release["canonical_provider_ids"]
    assert set(release["canonical_provider_ids"]) == {
        "vm100_local_ollama",
        "gpu_ollama",
        "ollama_cloud",
        "mistral_external",
    }


def test_v022_has_media_primitives_but_no_invoke_text_or_stt_capability() -> None:
    release = VERSIONS["v0.2.2"]
    sha = release["sha"]
    capabilities = module_contract(read_blob(sha, "src/ai_core/capabilities.py"))
    vision = module_contract(read_blob(sha, "src/ai_core/vision.py"))
    ocr = module_contract(read_blob(sha, "src/ai_core/ocr_pdf.py"))

    assert [
        item["name"]
        for item in capabilities["classes"]["ProviderCapability"]["enum_members"]
    ] == release["capability_enum"]
    assert set(release["capability_enum"]) == {
        "TEXT",
        "STRUCTURED_JSON",
        "VISION_IMAGE",
        "OCR_PDF",
    }
    assert "STT_SEGMENTS" not in release["capability_enum"]
    assert "invoke_vision" in vision["functions"]
    assert "invoke_pdf_ocr" in ocr["functions"]
    assert release["absent_inference_apis"] == ["invoke_text"]
    assert "invoke_text" not in release["root_exports"]
    assert all(
        "def invoke_text" not in read_blob(sha, path)
        for path in release["modules"]
    )


def test_each_v02_root_differs_from_the_current_main_contract() -> None:
    current_source = (Path(__file__).resolve().parents[2] / "src/ai_core/__init__.py").read_text(
        encoding="utf-8"
    )
    current_exports = module_contract(current_source)["exports"]

    assert all(
        release["root_exports"] != current_exports
        for tag, release in VERSIONS.items()
        if tag.startswith("v0.2.")
    )
