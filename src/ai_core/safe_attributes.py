from __future__ import annotations

from collections.abc import Mapping

SpanScalar = bool | int | float | str

SAFE_ATTRIBUTE_KEYS = frozenset({
    "workflow",
    "source_card_id",
    "source_entity_type",
    "source_entity_id",
    "llm.provider",
    "llm.model",
    "llm.latency_ms",
    "llm.input_tokens",
    "llm.output_tokens",
    "llm.status",
    "llm.error_category",
    "ai.adapter",
})


def sanitize_span_attributes(attributes: Mapping[str, object]) -> dict[str, SpanScalar]:
    return {
        key: value
        for key, value in attributes.items()
        if key in SAFE_ATTRIBUTE_KEYS and isinstance(value, (bool, int, float, str))
    }
