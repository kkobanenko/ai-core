from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType
import sys

import pytest

from tests.compatibility.git_ref import RefEvidenceError, read_blob


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "compatibility"
    / "privacy_conflicts.v1.json"
)
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _load_pr3_policy(sha: str) -> tuple[ModuleType, ModuleType]:
    try:
        catalog_source = read_blob(sha, "src/ai_core/provider_catalog.py")
        privacy_source = read_blob(sha, "src/ai_core/privacy.py")
    except RefEvidenceError:
        pytest.skip("pinned PR #3 object is unavailable in the local clone")
    names = ("ai_core", "ai_core.provider_catalog", "ai_core.privacy")
    missing = object()
    saved = {name: sys.modules.get(name, missing) for name in names}
    root = ModuleType("ai_core")
    root.__path__ = []
    catalog = ModuleType("ai_core.provider_catalog")
    catalog.__package__ = "ai_core"
    privacy = ModuleType("ai_core.privacy")
    privacy.__package__ = "ai_core"
    try:
        sys.modules["ai_core"] = root
        sys.modules["ai_core.provider_catalog"] = catalog
        exec(compile(catalog_source, "<pr3:provider_catalog.py>", "exec"), catalog.__dict__)
        sys.modules["ai_core.privacy"] = privacy
        exec(compile(privacy_source, "<pr3:privacy.py>", "exec"), privacy.__dict__)
        return catalog, privacy
    finally:
        for name, previous in saved.items():
            if previous is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def test_secret_matrix_denies_all_forms_and_boundaries_before_any_attempt() -> None:
    desired = FIXTURE["desired_contract"]
    rows = desired["rows"]

    assert len(rows) == 9
    assert {
        (row["outbound_form"], row["network_boundary"]) for row in rows
    } == {
        (form, boundary)
        for form in {"RAW", "SANITIZED", "SURROGATED"}
        for boundary in {"LOCAL_SAME_HOST", "EXTERNAL_CLOUD", "UNKNOWN_BOUNDARY"}
    }
    assert all(
        row["inference_execution"] == "denied"
        and row["eligible_routes"] == 0
        and row["provider_attempts"] == 0
        for row in rows
    )


def test_alias_sanitization_retry_and_fallback_cannot_weaken_secret_denial() -> None:
    desired = FIXTURE["desired_contract"]

    assert desired["preserving_transitions"] == [
        "alias_resolution",
        "sanitization",
        "retry",
        "fallback",
    ]
    for transition in desired["preserving_transitions"]:
        assert transition
        assert all(row["provider_attempts"] == 0 for row in desired["rows"])


def test_pr3_observed_policy_conflicts_on_sanitized_and_surrogated_secret() -> None:
    observed = FIXTURE["observed_pr3_conflict"]
    catalog, privacy = _load_pr3_policy(observed["head_sha"])
    profiles = catalog.get_provider_catalog()
    secret = privacy.DataClass.SECRET

    actual = {
        form.name: [
            provider_id
            for provider_id, profile in profiles.items()
            if privacy.is_eligible_for_outbound(profile, secret, form)
        ]
        for form in privacy.OutboundForm
    }

    assert actual["RAW"] == observed["RAW"]["eligible_provider_ids"] == []
    assert actual["SANITIZED"] == observed["SANITIZED"]["eligible_provider_ids"]
    assert actual["SURROGATED"] == observed["SURROGATED"]["eligible_provider_ids"]
    assert observed["conflicting_forms"] == ["SANITIZED", "SURROGATED"]
    assert observed["disposition"] == "REJECT / REDESIGN"
