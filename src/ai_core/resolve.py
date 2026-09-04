"""Резолв endpoint/credential из env-имён каталога (значения только из os.environ)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

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


def normalize_endpoint_base_url(
    raw: str,
    *,
    default_scheme: str = "",
    default_port: int | None = None,
) -> str:
    """Нормализовать endpoint из env по явным scheme/port метаданным профиля.

    Уже полный URL (http/https) — только убрать trailing slash.
    Bare host — собрать scheme://host[:default_port].
    host:port — scheme://host:port (не подставлять default_port).
    Без provider-id heuristics.
    """
    value = (raw or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return value.rstrip("/")
    scheme = (default_scheme or "").strip()
    if not scheme:
        # Нет метаданных схемы — не выдумываем URL.
        return value.rstrip("/")
    # Bare host или host:explicit_port (без схемы).
    host = value.rstrip("/")
    if ":" in host:
        # Уже указан порт — не добавляем default_port.
        return f"{scheme}://{host}"
    if default_port is not None:
        return f"{scheme}://{host}:{int(default_port)}"
    return f"{scheme}://{host}"


def resolve_provider_endpoint(
    provider_id: str,
    *,
    default_base_url: str = "",
) -> ResolvedProviderEndpoint:
    """Собрать endpoint из явных полей ProviderProfile (без name-heuristics)."""
    profile: ProviderProfile = get_provider_profile(provider_id)
    raw = _first_env(profile.endpoint_env_keys) or default_base_url.strip()
    base = normalize_endpoint_base_url(
        raw,
        default_scheme=profile.endpoint_default_scheme,
        default_port=profile.endpoint_default_port,
    )
    api_key = _first_env(profile.credential_env_keys)
    return ResolvedProviderEndpoint(
        provider_id=provider_id,
        base_url=base,
        api_key=api_key,
        api_key_optional=profile.api_key_optional,
    )
