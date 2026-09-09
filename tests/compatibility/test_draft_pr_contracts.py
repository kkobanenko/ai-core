from __future__ import annotations

import json
from pathlib import Path

from tests.compatibility.git_ref import read_blob


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "compatibility"
    / "draft_pr_contracts.v1.json"
)
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
PRS = FIXTURE["pull_requests"]
DISPOSITIONS = {
    "KEEP AS-IS",
    "KEEP AFTER FIX",
    "SPLIT INTO LATER WP",
    "REQUIRES GOVERNANCE DECISION",
    "REJECT / REDESIGN",
}


def _blocks(pr: str) -> dict[str, str]:
    return {
        block["name"]: block["disposition"]
        for block in PRS[pr]["logical_blocks"]
    }


def test_pr_evidence_is_pinned_and_uses_only_explicit_dispositions() -> None:
    assert FIXTURE["schema_version"] == 1
    assert set(PRS) == {"3", "4", "5"}
    assert PRS["3"]["head_sha"] == "4e26d67b825194e489a6a8b553c2a53dfea2a81f"
    assert PRS["4"]["head_sha"] == "1b2569a612968a3ac5099dea955cfccdcb191d52"
    assert PRS["5"]["head_sha"] == "25c269bb93dd37bd9b1556051972f5e1e60b34ad"
    for pr in PRS.values():
        assert (pr["state"], pr["draft"], pr["ci"], pr["review"]) == (
            "OPEN",
            True,
            "green",
            "none",
        )
        assert pr["logical_blocks"]
        assert all(block["disposition"] in DISPOSITIONS for block in pr["logical_blocks"])


def test_pr3_preserves_current_root_but_requires_secret_redesign() -> None:
    pr = PRS["3"]
    root_at_pr = read_blob(pr["head_sha"], "src/ai_core/__init__.py")
    root_at_base = read_blob(pr["base_sha"], "src/ai_core/__init__.py")
    blocks = _blocks("3")

    assert root_at_pr == root_at_base
    assert blocks["dependency-light submodules with unchanged root API"] == "KEEP AS-IS"
    assert blocks["SECRET eligibility after sanitization or surrogation"] == "REJECT / REDESIGN"
    assert blocks["catalog limited to four accepted provider identities"] == "REQUIRES GOVERNANCE DECISION"


def test_pr4_separates_accepted_alias_machinery_from_identity_and_stt_expansion() -> None:
    pr = PRS["4"]
    source = "\n".join(
        read_blob(pr["head_sha"], path)
        for path in (
            "src/ai_core/provider_aliases.py",
            "src/ai_core/provider_catalog.py",
            "src/ai_core/capabilities.py",
        )
    )
    blocks = _blocks("4")

    assert "gpu_whisper" in source
    assert "openai_external" in source
    assert "deepseek_external" in source
    assert "STT_SEGMENTS" in source
    assert blocks["fail-closed aliases limited to accepted identities"] == "KEEP AFTER FIX"
    assert blocks["gpu_whisper openai_external and deepseek_external identities"] == "SPLIT INTO LATER WP"
    assert blocks["STT_SEGMENTS records"] == "SPLIT INTO LATER WP"


def test_pr5_is_planning_only_and_keeps_policy_decisions_unresolved() -> None:
    pr = PRS["5"]
    sources = {
        path: read_blob(pr["head_sha"], path)
        for path in (
            "src/ai_core/budget.py",
            "src/ai_core/errors.py",
            "src/ai_core/health.py",
            "src/ai_core/routing.py",
        )
    }
    blocks = _blocks("5")

    assert all("httpx" not in source and "requests" not in source for source in sources.values())
    assert blocks["deterministic deadline arithmetic"] == "KEEP AS-IS"
    assert blocks["UNKNOWN health eligibility"] == "REQUIRES GOVERNANCE DECISION"
    assert blocks["caller order versus global priority hint"] == "REQUIRES GOVERNANCE DECISION"
    assert blocks["missing explicit egress allowlist treated as all providers"] == "REJECT / REDESIGN"
    assert blocks["retry fallback executor and provider transports"] == "SPLIT INTO LATER WP"


def test_fixtures_cannot_broaden_governance_or_implicitly_accept_unresolved_blocks() -> None:
    assert FIXTURE["implementation_authorized"] is False
    assert FIXTURE["accepted_provider_ids"] == [
        "vm100_local_ollama",
        "gpu_ollama",
        "ollama_cloud",
        "mistral_external",
    ]
    assert FIXTURE["pending_capabilities"] == ["STT_SEGMENTS"]
    for pr in PRS.values():
        for block in pr["logical_blocks"]:
            if block["disposition"] != "KEEP AS-IS":
                assert block["disposition"] in {
                    "KEEP AFTER FIX",
                    "SPLIT INTO LATER WP",
                    "REQUIRES GOVERNANCE DECISION",
                    "REJECT / REDESIGN",
                }
