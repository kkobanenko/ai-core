"""Pure shared-deadline / provider-attempt budget calculations."""

from __future__ import annotations

from dataclasses import dataclass

from ai_core.errors import RequestDeadlineExceededError


@dataclass(frozen=True)
class AttemptBudget:
    """Allocate bounded provider timeouts under one request deadline.

    The caller supplies monotonic timestamps. The budget never sleeps and never
    executes provider calls, which keeps fallback ownership outside this helper.
    """

    deadline_monotonic: float
    min_attempt_seconds: float = 0.1

    @classmethod
    def from_timeout(
        cls,
        *,
        now_monotonic: float,
        total_timeout_seconds: float,
        min_attempt_seconds: float = 0.1,
    ) -> "AttemptBudget":
        if total_timeout_seconds <= 0:
            raise ValueError("total_timeout_seconds must be > 0")
        if min_attempt_seconds <= 0:
            raise ValueError("min_attempt_seconds must be > 0")
        return cls(
            deadline_monotonic=now_monotonic + total_timeout_seconds,
            min_attempt_seconds=min_attempt_seconds,
        )

    def remaining_seconds(self, *, now_monotonic: float) -> float:
        return max(0.0, self.deadline_monotonic - now_monotonic)

    def timeout_for_attempt(
        self,
        *,
        now_monotonic: float,
        configured_timeout_seconds: float,
        future_attempts: int = 0,
        reserve_per_future_attempt_seconds: float = 0.0,
    ) -> float:
        """Return the maximum timeout allowed for the next provider attempt.

        `future_attempts` plus `reserve_per_future_attempt_seconds` prevents one
        provider from consuming the entire shared deadline when fallback remains.
        """

        if configured_timeout_seconds <= 0:
            raise ValueError("configured_timeout_seconds must be > 0")
        if future_attempts < 0:
            raise ValueError("future_attempts must be >= 0")
        if reserve_per_future_attempt_seconds < 0:
            raise ValueError("reserve_per_future_attempt_seconds must be >= 0")

        remaining = self.remaining_seconds(now_monotonic=now_monotonic)
        reserved = future_attempts * reserve_per_future_attempt_seconds
        available = remaining - reserved
        if available < self.min_attempt_seconds:
            raise RequestDeadlineExceededError(
                "Shared request deadline leaves no safe budget for another provider attempt"
            )
        return min(configured_timeout_seconds, available)
