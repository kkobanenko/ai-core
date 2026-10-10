"""Fail-closed admission for Laya shadow HTTP endpoints (LOCAL_SAME_HOST)."""

from __future__ import annotations

import ipaddress
import os
import socket
import urllib.parse
from dataclasses import dataclass
from typing import Iterable

from ai_core.provider_catalog import NetworkBoundary

_MAX_RESPONSE_BYTES = 256_000
_ALLOWED_SCHEMES = frozenset({"http"})


@dataclass(frozen=True)
class EndpointAdmission:
    url: str
    host: str
    port: int


class EndpointAdmissionError(ValueError):
    """Endpoint rejected for shadow LOCAL_SAME_HOST transport."""


def strip_proxy_env() -> dict[str, str | None]:
    """Snapshot proxy-related env vars and clear them for the duration of a local call."""
    keys = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    )
    saved: dict[str, str | None] = {}
    for key in keys:
        saved[key] = os.environ.pop(key, None)
    return saved


def restore_proxy_env(saved: dict[str, str | None]) -> None:
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _iter_resolved_ips(host: str, port: int) -> Iterable[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise EndpointAdmissionError(f"cannot resolve endpoint host: {host}") from exc
    for _family, _type, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        yield ipaddress.ip_address(ip_str)


def _is_loopback_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(addr.is_loopback)


def admit_laya_shadow_endpoint(
    raw_url: str,
    *,
    network_boundary: NetworkBoundary,
    request_egress_authorized: bool,
) -> EndpointAdmission:
    """Validate URL for shadow inference. LOCAL_SAME_HOST must stay on loopback."""
    url = (raw_url or "").strip()
    if not url:
        raise EndpointAdmissionError("empty endpoint")

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise EndpointAdmissionError(f"unsupported scheme: {parsed.scheme!r}")

    host = (parsed.hostname or "").lower().strip()
    if not host:
        raise EndpointAdmissionError("missing hostname")

    port = parsed.port
    if port is None:
        port = 80 if parsed.scheme == "http" else 443

    if network_boundary is NetworkBoundary.LOCAL_SAME_HOST:
        if host not in ("localhost", "127.0.0.1", "::1") and not host.endswith(".localhost"):
            raise EndpointAdmissionError("LOCAL_SAME_HOST requires loopback hostname")
        for addr in _iter_resolved_ips(host, port):
            if not _is_loopback_ip(addr):
                raise EndpointAdmissionError("resolved endpoint is not loopback")
    elif request_egress_authorized is not True:
        raise EndpointAdmissionError("remote Laya endpoint requires explicit egress authorization")

    return EndpointAdmission(url=url, host=host, port=port)


def bounded_response_bytes(raw: bytes) -> bytes:
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise EndpointAdmissionError("provider response too large")
    return raw
