from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    transport: str
    model: str
    base_url: str
    api_key: str
    api_key_optional: bool
    timeout_seconds: float
    headers: dict[str, str] | None = None

    def is_ready(self) -> bool:
        endpoint_ready = bool(self.base_url) or self.name == "openai"
        return bool(self.model and endpoint_ready and (self.api_key or self.api_key_optional))


@dataclass(frozen=True)
class AttemptRecord:
    provider: str
    model: str
    attempt_index: int
    outcome: str
    reason: str
    latency_ms: int


@dataclass(frozen=True)
class JsonCompletion:
    raw_content: str
    provider_name: str
    model_name: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    attempt_summary: tuple[dict[str, Any], ...] = ()
