"""Endpoint admission for Laya shadow HTTP."""

from __future__ import annotations

import pytest

from ai_core.judgment_laya_endpoint import EndpointAdmissionError, admit_laya_shadow_endpoint
from ai_core.provider_catalog import NetworkBoundary


def test_loopback_http_allowed() -> None:
    admitted = admit_laya_shadow_endpoint(
        "http://127.0.0.1:8080/v1/judge",
        network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
        request_egress_authorized=False,
    )
    assert admitted.port == 8080


def test_remote_host_rejected_for_local_boundary() -> None:
    with pytest.raises(EndpointAdmissionError):
        admit_laya_shadow_endpoint(
            "http://192.168.1.10:8080/v1/judge",
            network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
            request_egress_authorized=False,
        )


def test_https_scheme_rejected() -> None:
    with pytest.raises(EndpointAdmissionError):
        admit_laya_shadow_endpoint(
            "https://127.0.0.1:8080/v1/judge",
            network_boundary=NetworkBoundary.LOCAL_SAME_HOST,
            request_egress_authorized=False,
        )
