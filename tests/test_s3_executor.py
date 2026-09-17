"""S3 Executor Facade Tests: verify execute_chat and execute_prompt ergonomics."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import ai_core
from ai_core.capabilities import ProviderCapability
from ai_core.errors import (
    AiErrorKind,
    AllCandidatesExhaustedError,
    ErrorDescriptor,
    NoEligibleProviderError,
)
from ai_core.executor import (
    DEFAULT_CANDIDATES,
    execute_chat,
    execute_prompt,
)
from ai_core.health import ProviderHealthStore
from ai_core.routing import RouteCandidate
from ai_core.transports import (
    ProviderTransport,
    TransportAttemptResult,
    TransportResponse,
    TransportUsage,
)

LOCAL_CANDIDATE = RouteCandidate(provider_id="vm100_local_ollama", model="qwen3:8b")
GPU_CANDIDATE = RouteCandidate(provider_id="gpu_ollama", model="qwen3:8b")
EXTERNAL_CANDIDATE = RouteCandidate(provider_id="mistral_external", model="mistral-small-latest")


def _mock_success(candidate: RouteCandidate, content: str = "pong") -> TransportAttemptResult:
    return TransportAttemptResult(
        candidate=candidate,
        response=TransportResponse(
            candidate=candidate,
            content=content,
            usage=TransportUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            latency_seconds=0.15,
            raw_response={"message": {"content": content}},
        ),
        error=None,
        latency_seconds=0.15,
    )


def _mock_error(candidate: RouteCandidate, kind: AiErrorKind = AiErrorKind.TIMEOUT) -> TransportAttemptResult:
    return TransportAttemptResult(
        candidate=candidate,
        response=None,
        error=ErrorDescriptor(
            kind=kind,
            status_code=504,
            retryable_same_provider=True,
            fallback_eligible=True,
            terminal=False,
        ),
        latency_seconds=1.0,
    )


class TestExecutorFacade:
    """Tests for execute_chat and execute_prompt facades."""

    def test_execute_chat_default_pipeline_success(self) -> None:
        mock_transport = MagicMock(spec=ProviderTransport)
        mock_transport.send_attempt.return_value = _mock_success(LOCAL_CANDIDATE, "Hello from local!")

        result = execute_chat(
            messages=[{"role": "user", "content": "Hi"}],
            transport=mock_transport,
        )

        assert result.winner == LOCAL_CANDIDATE
        assert result.content == "Hello from local!"
        assert not result.fallback_occurred
        assert len(result.attempts) == 1
        assert mock_transport.send_attempt.call_count == 1

    def test_execute_chat_fallback_flow(self) -> None:
        mock_transport = MagicMock(spec=ProviderTransport)
        mock_transport.send_attempt.side_effect = [
            _mock_error(LOCAL_CANDIDATE, kind=AiErrorKind.TIMEOUT),
            _mock_success(GPU_CANDIDATE, "Hello from GPU fallback!"),
        ]

        result = execute_chat(
            messages=[{"role": "user", "content": "Hi"}],
            request_egress_authorized=True,
            transport=mock_transport,
        )

        assert result.winner == GPU_CANDIDATE
        assert result.content == "Hello from GPU fallback!"
        assert result.fallback_occurred
        assert len(result.attempts) == 2

    def test_execute_prompt_converts_strings_to_messages(self) -> None:
        mock_transport = MagicMock(spec=ProviderTransport)
        mock_transport.send_attempt.return_value = _mock_success(LOCAL_CANDIDATE, "4")

        result = execute_prompt(
            prompt="2 + 2?",
            system_prompt="You are a math tutor.",
            transport=mock_transport,
        )

        assert result.content == "4"
        call_req = mock_transport.send_attempt.call_args[0][0]
        assert len(call_req.messages) == 2
        assert call_req.messages[0] == {"role": "system", "content": "You are a math tutor."}
        assert call_req.messages[1] == {"role": "user", "content": "2 + 2?"}

    def test_execute_chat_privacy_denied_external_candidate_without_egress(self) -> None:
        """When only external candidates are provided and egress is not authorized, plan raises NoEligibleProviderError."""
        mock_transport = MagicMock(spec=ProviderTransport)

        with pytest.raises(NoEligibleProviderError, match="No candidate survived"):
            execute_chat(
                messages=[{"role": "user", "content": "Hi"}],
                candidates=[EXTERNAL_CANDIDATE],
                request_egress_authorized=False,
                transport=mock_transport,
            )

        # Transport never called when router rejects candidates
        mock_transport.send_attempt.assert_not_called()

    def test_execute_chat_external_succeeds_when_egress_authorized(self) -> None:
        mock_transport = MagicMock(spec=ProviderTransport)
        mock_transport.send_attempt.return_value = _mock_success(EXTERNAL_CANDIDATE, "Bonjour!")

        result = execute_chat(
            messages=[{"role": "user", "content": "Bonjour"}],
            candidates=[EXTERNAL_CANDIDATE],
            request_egress_authorized=True,
            transport=mock_transport,
        )

        assert result.winner == EXTERNAL_CANDIDATE
        assert result.content == "Bonjour!"

    def test_root_api_exact_nine_symbols_invariant_preserved(self) -> None:
        """S3 implementation must NOT alter or pollute the root ai_core.__all__ contract."""
        expected = {
            "AttributeValue",
            "PhoenixConfig",
            "init_tracing",
            "load_phoenix_config",
            "maybe_truncate",
            "record_llm_result",
            "sanitize_attributes",
            "shutdown_tracing",
            "start_llm_span",
        }
        assert set(ai_core.__all__) == expected
        assert len(ai_core.__all__) == 9
