"""Резолв endpoint/credential из env-имён каталога (значения только из os.environ)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ai_core.provider_catalog import ProviderProfile, get_provider_profile


@dataclass(frozen=True)
class ResolvedProviderEndpoint:
    """Runtime endpoint: base_url + optional api_key. Секрет не попадает в repr."""

    provider_id: str
    base_url: str
    api_key: str
    api_key_optional: bool

    def __repr__(self) -> str:
        key_state = "set" if self.api_key else "empty"
        return (
            f"ResolvedProviderEndpoint(provider_id={self.provider_id!r}, "
            f"base_url={self.base_url!r}, api_key=<{key_state}>)"
        )

    def __str__(self) -> str:
        return repr(self)


def _first_env(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def resolve_provider_endpoint(
    provider_id: str,
    *,
    default_base_url: str = "",
) -> ResolvedProviderEndpoint:
    """Собрать endpoint из явных полей ProviderProfile (без name-heuristics)."""
    profile: ProviderProfile = get_provider_profile(provider_id)
    base = _first_env(profile.endpoint_env_keys) or default_base_url.strip()
    api_key = _first_env(profile.credential_env_keys)
    return ResolvedProviderEndpoint(
        provider_id=provider_id,
        base_url=base.rstrip("/"),
        api_key=api_key,
        api_key_optional=profile.api_key_optional,
    )
