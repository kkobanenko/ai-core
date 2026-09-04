"""Общие request/result типы для media (vision / PDF OCR). Без product IDs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class VisionImageRequest:
    """Один вызов vision: изображения + prompt (prompt задаёт consumer)."""

    model: str
    images: tuple[bytes | str, ...]
    prompt: str
    timeout_seconds: float = 120.0


@dataclass(frozen=True)
class OcrPdfRequest:
    """Один вызов PDF OCR: байты PDF (без MinIO/путей)."""

    model: str
    pdf_bytes: bytes
    max_pages: int = 10
    timeout_seconds: float = 120.0


@dataclass(frozen=True)
class MediaResult:
    """Нормализованный результат media-примитива (без секретов и полных байт)."""

    text: str
    provider_id: str
    model: str
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    page_count: int = 0
    image_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        # Не печатаем полный OCR text в repr (может быть длинным/чувствительным).
        preview = (self.text[:40] + "…") if len(self.text) > 40 else self.text
        return (
            f"MediaResult(provider_id={self.provider_id!r}, model={self.model!r}, "
            f"latency_ms={self.latency_ms}, chars={len(self.text)}, text_preview={preview!r})"
        )
