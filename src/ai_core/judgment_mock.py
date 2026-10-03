"""Deterministic J1 mock execution. Test-only. Not a production provider.

This module provides mock_judgment execution for J1 contract tests.
No network. No credentials. No provider SDK. Not catalog-admitted.
Protocol conformance != execution admission.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from ai_core.judgment_contracts import (
    Choice,
    JudgmentErrorCategory,
    JudgmentOutcome,
    JudgmentRequest,
    JudgmentResponse,
    JudgmentTelemetry,
    Noul,
    NoulReason,
    Score,
)

MOCK_PROVIDER_ID = "mock_judgment"


class MockVariant(str, Enum):
    """Declared mock result variant."""

    CHOICE = "choice"
    NOUL = "noul"
    ERROR = "error"
    INVALID_RESPONSE = "invalid_response"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class MockBehavior:
    """Bounded, deterministic mock behavior fixture. Data only, not executable code."""

    variant: MockVariant = MockVariant.CHOICE
    choice_value: str | None = None
    score: Score | None = None
    noul_reason: NoulReason = NoulReason.NO_RELIABLE_JUDGMENT
    error_category: JudgmentErrorCategory = JudgmentErrorCategory.PROVIDER_UNAVAILABLE
    timeout_seconds: float = 0.05
    invalid_provider_name: str | None = None


class DeterministicMockJudgmentProvider:
    """Repository-owned deterministic mock judgment provider.

    No network, no credentials, no subprocess, no environment lookup, no provider SDK.
    """

    def __init__(self, behavior: MockBehavior | None = None) -> None:
        self.behavior = behavior or MockBehavior()

    def judge(self, request: JudgmentRequest) -> JudgmentResponse:
        b = self.behavior
        if b.variant == MockVariant.TIMEOUT:
            time.sleep(b.timeout_seconds)

        if b.variant == MockVariant.INVALID_RESPONSE:
            # Produce an invalid response (e.g. wrong provider or undeclared choice)
            provider_name = b.invalid_provider_name or "unadmitted_foreign_provider"
            tel = JudgmentTelemetry(
                outcome=JudgmentOutcome.CHOICE,
                error_category=None,
                latency_ms=0,
                retry_count=0,
                provider=provider_name,
                model=request.model,
                model_version=request.model_version,
                decision_pack_id=request.decision_pack_id,
                decision_pack_version=request.decision_pack_version,
            )
            return JudgmentResponse(
                provider=provider_name,
                model=request.model,
                model_version=request.model_version,
                decision_pack_id=request.decision_pack_id,
                decision_pack_version=request.decision_pack_version,
                telemetry=tel,
                choice=Choice(b.choice_value or "undeclared_choice_xyz"),
            )

        if b.variant == MockVariant.ERROR:
            tel = JudgmentTelemetry(
                outcome=JudgmentOutcome.ERROR,
                error_category=b.error_category,
                latency_ms=0,
                retry_count=0,
                provider=request.provider,
                model=request.model,
                model_version=request.model_version,
                decision_pack_id=request.decision_pack_id,
                decision_pack_version=request.decision_pack_version,
            )
            return JudgmentResponse(
                provider=request.provider,
                model=request.model,
                model_version=request.model_version,
                decision_pack_id=request.decision_pack_id,
                decision_pack_version=request.decision_pack_version,
                telemetry=tel,
                error=b.error_category,
            )

        if b.variant == MockVariant.NOUL:
            tel = JudgmentTelemetry(
                outcome=JudgmentOutcome.NOUL,
                error_category=None,
                latency_ms=0,
                retry_count=0,
                provider=request.provider,
                model=request.model,
                model_version=request.model_version,
                decision_pack_id=request.decision_pack_id,
                decision_pack_version=request.decision_pack_version,
            )
            return JudgmentResponse(
                provider=request.provider,
                model=request.model,
                model_version=request.model_version,
                decision_pack_id=request.decision_pack_id,
                decision_pack_version=request.decision_pack_version,
                telemetry=tel,
                noul=Noul(reason_code=b.noul_reason),
            )

        # CHOICE (default or TIMEOUT if returned before deadline)
        choice_val = b.choice_value or (request.allowed_choices[0] if request.allowed_choices else "yes")
        tel = JudgmentTelemetry(
            outcome=JudgmentOutcome.CHOICE,
            error_category=None,
            latency_ms=0,
            retry_count=0,
            provider=request.provider,
            model=request.model,
            model_version=request.model_version,
            decision_pack_id=request.decision_pack_id,
            decision_pack_version=request.decision_pack_version,
        )
        return JudgmentResponse(
            provider=request.provider,
            model=request.model,
            model_version=request.model_version,
            decision_pack_id=request.decision_pack_id,
            decision_pack_version=request.decision_pack_version,
            telemetry=tel,
            choice=Choice(value=choice_val),
            score=b.score,
        )


__all__ = [
    "DeterministicMockJudgmentProvider",
    "MOCK_PROVIDER_ID",
    "MockBehavior",
    "MockVariant",
]
