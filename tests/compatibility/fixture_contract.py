"""Validation for portable, content-free consumer compatibility evidence."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit


EXPECTED_CONSUMERS = {
    "prozakupki",
    "kmo",
    "zoom",
    "clin_rec",
    "landing_sell",
    "agent_lab",
    "alpha_university",
    "transcription_service",
    "image_description_service",
}
ACCEPTED_PROVIDER_IDS = [
    "vm100_local_ollama",
    "gpu_ollama",
    "ollama_cloud",
    "mistral_external",
]
REQUIRED_SECTIONS = {
    "observed_evidence",
    "consumer_requirement",
    "accepted_platform_contract",
    "proposed_behavior",
    "governance_pending",
}
REQUIRED_CONSUMER_KEYS = REQUIRED_SECTIONS | {
    "provenance",
    "current_path",
    "ai_core_pin",
    "capability_requirements",
    "retry",
    "fallback_owner",
    "privacy",
    "tracing",
    "rollback",
    "gaps",
    "risk",
    "representable",
}
REQUIRED_PROVENANCE_KEYS = {
    "repository",
    "sha",
    "ref",
    "role",
    "authority",
    "paths",
}
FORBIDDEN_CONTENT_KEYS = {
    "api_key",
    "credential",
    "credentials",
    "password",
    "payload",
    "prompt",
    "prompts",
    "schema",
    "secret",
    "secret_value",
    "token",
}
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def load_consumer_contracts(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("consumer fixture root must be an object")
    return data


def _walk(value: object, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, key, child
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            yield child_path, None, child
            yield from _walk(child, child_path)


def _unsafe_url(value: str) -> bool:
    if not value.startswith(("http://", "https://")):
        return False
    parsed = urlsplit(value)
    return bool(parsed.username or parsed.password or parsed.query or parsed.fragment)


def _credential_shaped(value: str) -> bool:
    lowered = value.lower()
    return (
        lowered.startswith(("sk-", "bearer ", "basic "))
        or "-----begin private key-----" in lowered
    )


def validate_consumer_contracts(data: object) -> list[str]:
    """Return JSON-path diagnostics while never echoing fixture values."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["$: expected object"]

    if data.get("schema_version") != 1:
        errors.append("$.schema_version: expected 1")
    if data.get("accepted_provider_ids") != ACCEPTED_PROVIDER_IDS:
        errors.append("$.accepted_provider_ids: must equal the governance allowlist")
    if data.get("implementation_authorized") is not False:
        errors.append("$.implementation_authorized: must remain false")
    accepted_capabilities = data.get("accepted_capabilities")
    if not isinstance(accepted_capabilities, list):
        errors.append("$.accepted_capabilities: expected list")
    elif "STT_SEGMENTS" in accepted_capabilities:
        errors.append("$.accepted_capabilities: STT_SEGMENTS is not accepted")
    pending_capabilities = data.get("governance_pending_capabilities")
    if not isinstance(pending_capabilities, list) or "STT_SEGMENTS" not in pending_capabilities:
        errors.append("$.governance_pending_capabilities: STT_SEGMENTS must remain pending")

    consumers = data.get("consumers")
    if not isinstance(consumers, dict):
        errors.append("$.consumers: expected object")
    elif set(consumers) != EXPECTED_CONSUMERS:
        errors.append("$.consumers: expected exactly the nine recorded consumers")
    else:
        for name, consumer in consumers.items():
            base = f"$.consumers.{name}"
            if not isinstance(consumer, dict):
                errors.append(f"{base}: expected object")
                continue
            for key in sorted(REQUIRED_CONSUMER_KEYS - set(consumer)):
                errors.append(f"{base}.{key}: required")
            provenance = consumer.get("provenance")
            if not isinstance(provenance, dict):
                errors.append(f"{base}.provenance: expected object")
            else:
                for key in sorted(REQUIRED_PROVENANCE_KEYS - set(provenance)):
                    errors.append(f"{base}.provenance.{key}: required")
                sha = provenance.get("sha")
                if not isinstance(sha, str) or not _SHA_RE.fullmatch(sha):
                    errors.append(f"{base}.provenance.sha: expected exact commit SHA")
                paths = provenance.get("paths")
                if not isinstance(paths, list) or not paths or not all(
                    isinstance(item, str) and item for item in paths
                ):
                    errors.append(f"{base}.provenance.paths: expected nonempty path list")
            for section in REQUIRED_SECTIONS:
                if section in consumer and not isinstance(consumer[section], dict):
                    errors.append(f"{base}.{section}: expected object")
            retry = consumer.get("retry")
            if not isinstance(retry, dict):
                errors.append(f"{base}.retry: expected object")
            else:
                expected_retry = {"provider_call", "provider_fallback", "durable_job"}
                if set(retry) != expected_retry:
                    for key in sorted(expected_retry - set(retry)):
                        errors.append(f"{base}.retry.{key}: required")
                if not all(isinstance(item, dict) for item in retry.values()):
                    errors.append(f"{base}.retry: retry levels must be objects")
            if consumer.get("fallback_owner") not in {
                "ai_core_v02_client",
                "consumer",
                "none",
            }:
                errors.append(f"{base}.fallback_owner: invalid owner")
            if consumer.get("representable") not in {"yes", "partial", "blocked"}:
                errors.append(f"{base}.representable: invalid state")
            if not isinstance(consumer.get("capability_requirements"), list):
                errors.append(f"{base}.capability_requirements: expected list")
            if not isinstance(consumer.get("gaps"), list):
                errors.append(f"{base}.gaps: expected list")
            if not isinstance(consumer.get("risk"), str):
                errors.append(f"{base}.risk: expected string")
            if not isinstance(consumer.get("rollback"), dict):
                errors.append(f"{base}.rollback: expected object")

    for path, key, value in _walk(data):
        if key is not None and key.lower() in FORBIDDEN_CONTENT_KEYS:
            errors.append(f"{path}: content or credential field is forbidden")
        if isinstance(value, str) and (_unsafe_url(value) or _credential_shaped(value)):
            errors.append(f"{path}: unsafe URL or credential-shaped value")

    return errors
