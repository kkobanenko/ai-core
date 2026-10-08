"""Consumer route contract for SLS-REQ-002: no implicit or VM100 fallbacks."""

from __future__ import annotations

from ai_core.capabilities import ProviderCapability
from ai_core.errors import AiErrorKind, ErrorDescriptor
from ai_core.executor import execute_chat
from ai_core.privacy import DataClass, OutboundForm
from ai_core.routing import CapabilityAuthorization, RouteCandidate, RoutePolicy
from ai_core.transports import TransportAttemptResult, TransportResponse, TransportUsage


GPU = RouteCandidate("gpu_ollama", "qwen3:8b")
CLOUD = RouteCandidate("ollama_cloud", "gpt-oss:20b-cloud")
MISTRAL = RouteCandidate("mistral_external", "mistral-small-latest")
PRODUCT_CANDIDATES = (GPU, CLOUD, MISTRAL)


class _FakeTransport:
    def __init__(self, *, first_fails: bool):
        self.calls = []
        self.first_fails = first_fails

    def send_attempt(self, request):
        self.calls.append(request.candidate)
        if self.first_fails and request.candidate == GPU:
            return TransportAttemptResult(
                candidate=request.candidate,
                response=None,
                error=ErrorDescriptor(AiErrorKind.SERVER, 503, False, True, False),
                latency_seconds=0.01,
            )
        return TransportAttemptResult(
            candidate=request.candidate,
            response=TransportResponse(
                candidate=request.candidate,
                content='{"suggestions":["A","B","C"]}',
                usage=TransportUsage(1, 1, 2),
                latency_seconds=0.01,
                raw_response={},
            ),
            error=None,
            latency_seconds=0.01,
        )


def _policy(egress: bool):
    return RoutePolicy(
        authorized_provider_ids=frozenset(c.provider_id for c in PRODUCT_CANDIDATES),
        capability_authorizations=frozenset(
            CapabilityAuthorization(c.provider_id, c.model, ProviderCapability.TEXT)
            for c in PRODUCT_CANDIDATES
        ),
        request_egress_authorized=egress,
    )


def _chat(fake, egress: bool):
    return execute_chat(
        messages=[{"role": "user", "content": "Sanitized public question"}],
        candidates=PRODUCT_CANDIDATES,
        policy=_policy(egress),
        data_class=DataClass.PUBLIC_NO_PII,
        outbound_form=OutboundForm.SANITIZED,
        request_egress_authorized=egress,
        transport=fake,
    )


def test_gpu_only_without_external_egress():
    fake = _FakeTransport(first_fails=False)
    result = _chat(fake, egress=False)
    assert result.winner == GPU
    assert fake.calls == [GPU]
    assert all(c.provider_id != "vm100_local_ollama" for c in fake.calls)


def test_gpu_failure_routes_to_cloud_only_with_egress():
    fake = _FakeTransport(first_fails=True)
    result = _chat(fake, egress=True)
    assert result.winner == CLOUD
    assert fake.calls == [GPU, CLOUD]
    assert all(c.provider_id != "vm100_local_ollama" for c in fake.calls)
