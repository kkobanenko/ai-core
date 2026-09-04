from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

SpanScalar = bool | int | float | str

_logger = logging.getLogger(__name__)

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
    # AU01B media (namespaced; не дублировать allowlist в vision/ocr).
    "ai.capability",
    "media.page_count",
    "media.image_count",
    "media.page_count_requested",
})


def sanitize_span_attributes(attributes: Mapping[str, object]) -> dict[str, SpanScalar]:
    return {
        key: value
        for key, value in attributes.items()
        if key in SAFE_ATTRIBUTE_KEYS and isinstance(value, (bool, int, float, str))
    }


def set_safe_span_attributes(span: Any, attributes: Mapping[str, object]) -> None:
    """Прогнать атрибуты через общий allowlist и soft-set на span.

    Не бросает в бизнес-логику. span=None — no-op.
    """
    if span is None:
        return
    for key, value in sanitize_span_attributes(attributes).items():
        try:
            span.set_attribute(key, value)
        except Exception as error:
            _logger.warning("phoenix span attribute failed key=%s error=%s", key, error)
