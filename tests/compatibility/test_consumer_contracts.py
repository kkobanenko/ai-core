from __future__ import annotations

from pathlib import Path

from tests.compatibility.fixture_contract import load_consumer_contracts


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "compatibility"
    / "consumer_contracts.v1.json"
)
DATA = load_consumer_contracts(FIXTURE_PATH)
CONSUMERS = DATA["consumers"]


def test_every_consumer_separates_three_retry_levels_and_one_fallback_owner() -> None:
    for consumer in CONSUMERS.values():
        assert set(consumer["retry"]) == {
            "provider_call",
            "provider_fallback",
            "durable_job",
        }
        assert consumer["fallback_owner"] in {
            "ai_core_v02_client",
            "consumer",
            "none",
        }


def test_every_consumer_keeps_an_explicit_old_path_rollback() -> None:
    for consumer in CONSUMERS.values():
        assert consumer["rollback"]["old_path"]
        assert consumer["rollback"]["activation"] in {
            "configuration_switch",
            "package_pin",
            "no_change_required",
        }


def test_capability_evidence_is_model_or_path_specific() -> None:
    for consumer in CONSUMERS.values():
        for requirement in consumer["capability_requirements"]:
            assert requirement["capability"]
            assert requirement["evidence_scope"] in {"model", "execution_path"}
            assert requirement["evidence_level"] in {
                "configured",
                "unit_tested",
                "integration_tested",
                "runtime_observed",
                "not_applicable",
            }


def test_blocked_or_partial_consumers_name_gaps_and_questions() -> None:
    for consumer in CONSUMERS.values():
        if consumer["representable"] in {"blocked", "partial"}:
            assert consumer["gaps"]
            assert consumer["governance_pending"]["questions"]


def test_alpha_has_no_current_ai_core_or_llm_runtime_dependency() -> None:
    alpha = CONSUMERS["alpha_university"]

    assert alpha["current_path"] == "deterministic_planner_and_tesseract_ocr_shadow"
    assert alpha["ai_core_pin"] == "none"
    assert alpha["fallback_owner"] == "none"
    assert alpha["accepted_platform_contract"]["runtime_status"] == "no_ai_runtime"


def test_media_clients_record_expected_contract_without_claiming_a_server() -> None:
    for name, endpoint in {
        "transcription_service": "/internal/ai/v1/transcriptions",
        "image_description_service": "/internal/ai/v1/image-descriptions",
    }.items():
        consumer = CONSUMERS[name]
        contract = consumer["consumer_requirement"]["http_contract"]
        assert contract["endpoint"] == endpoint
        assert contract["header_name"] == "X-Prozakupki-AI-Key"
        assert contract["contract_version"] == 1
        assert contract["client_timeout_seconds"] == 150
        assert contract["raw_body_logging"] == "forbidden"
        assert consumer["retry"]["durable_job"]["max_attempts"] == 3
        assert consumer["current_path"] == "fake_default_optional_ai_core_http_client"
        assert consumer["proposed_behavior"]["canonical_server_exists"] is False
        assert consumer["representable"] == "blocked"


def test_unaccepted_identifiers_and_stt_remain_governance_pending() -> None:
    assert DATA["accepted_provider_ids"] == [
        "vm100_local_ollama",
        "gpu_ollama",
        "ollama_cloud",
        "mistral_external",
    ]
    pending = DATA["governance_pending_capabilities"]
    assert "STT_SEGMENTS" in pending
    assert "STT_SEGMENTS" not in DATA["accepted_capabilities"]
    assert DATA["implementation_authorized"] is False
