"""Single-provider Mistral PDF OCR: ровно один HTTP POST на invoke_pdf_ocr."""

from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from ai_core.capabilities import ProviderCapability
from ai_core.media import MediaResult, OcrPdfRequest
from ai_core.media_errors import MediaAuthError, MediaTransportError, classify_http_error
from ai_core.media_gate import assert_media_allowed
from ai_core.privacy import DataClass, OutboundForm
from ai_core.provider_catalog import PROVIDER_MISTRAL_EXTERNAL
from ai_core.resolve import resolve_provider_endpoint
from ai_core.safe_attributes import set_safe_span_attributes
from ai_core.tracing import start_llm_span

# Публичный default base (не секрет); endpoint всё же предпочитает env.
MISTRAL_OCR_DEFAULT_BASE_URL = "https://api.mistral.ai/v1"


def build_mistral_pages_param(max_pages: int) -> str:
    """Строка pages для Mistral API (0-based inclusive), как в Prozakupki."""
    pages = max(1, int(max_pages))
    if pages == 1:
        return "0"
    return f"0-{pages - 1}"


def build_mistral_ocr_payload(
    *,
    model: str,
    pdf_bytes: bytes,
    max_pages: int,
) -> dict[str, Any]:
    """Собрать wire payload. Base64 здесь — только encoding, не sanitization."""
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    return {
        "model": model,
        "document": {
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{encoded}",
        },
        "pages": build_mistral_pages_param(max_pages),
    }


def _parse_mistral_pages(body: dict[str, Any]) -> tuple[str, int]:
    page_rows = body.get("pages") or []
    parts: list[str] = []
    for row in page_rows:
        if not isinstance(row, dict):
            continue
        markdown = str(row.get("markdown") or "").strip()
        if markdown:
            parts.append(markdown)
    usage = body.get("usage_info") or {}
    page_count = int(usage.get("pages_processed") or len(page_rows) or 0)
    return "\n\n".join(parts), page_count


def invoke_pdf_ocr(
    request: OcrPdfRequest,
    *,
    data_class: DataClass,
    outbound_form: OutboundForm,
    provider_id: str = PROVIDER_MISTRAL_EXTERNAL,
    client: httpx.Client | None = None,
) -> MediaResult:
    """Один upstream-вызов Mistral OCR. Без retry/fallback/другого провайдера.

    data_class и outbound_form обязательны (keyword-only): fail-open defaults запрещены.
    Неизменённые PDF bytes = OutboundForm.RAW (base64 ≠ sanitization).
    """
    assert_media_allowed(
        provider_id=provider_id,
        model=request.model,
        capability=ProviderCapability.OCR_PDF,
        data_class=data_class,
        outbound_form=outbound_form,
    )
    if not request.pdf_bytes:
        raise ValueError("pdf_bytes is empty")

    endpoint = resolve_provider_endpoint(
        provider_id,
        default_base_url=MISTRAL_OCR_DEFAULT_BASE_URL,
    )
    if not endpoint.api_key:
        # Терминальная config/auth — не transport fallback.
        raise MediaAuthError("Missing MISTRAL_API_KEY for mistral_external", status_code=None)

    payload = build_mistral_ocr_payload(
        model=request.model,
        pdf_bytes=request.pdf_bytes,
        max_pages=request.max_pages,
    )
    # Не кладём api_key в локальные переменные сообщений об ошибках.
    headers = {
        "Authorization": f"Bearer {endpoint.api_key}",
        "Content-Type": "application/json",
    }
    url = f"{endpoint.base_url.rstrip('/')}/ocr"

    owned = client is None
    http = client or httpx.Client(timeout=request.timeout_seconds)
    started = time.perf_counter()
    page_count_requested = max(1, int(request.max_pages))
    attrs = {
        "llm.provider": provider_id,
        "llm.model": request.model,
        "ai.capability": ProviderCapability.OCR_PDF.value,
        "media.page_count_requested": page_count_requested,
    }
    try:
        with start_llm_span(workflow="ai_core.invoke_pdf_ocr", attributes=attrs) as span:
            try:
                response = http.post(url, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                raise MediaTransportError("mistral ocr timeout", category="timeout") from exc
            except httpx.TransportError as exc:
                raise MediaTransportError(
                    f"mistral ocr transport error: {exc.__class__.__name__}",
                    category="connection",
                ) from exc

            if response.status_code >= 400:
                raise classify_http_error(
                    response.status_code,
                    f"mistral ocr HTTP {response.status_code}",
                )

            body = response.json()
            latency_ms = int((time.perf_counter() - started) * 1000)
            text, page_count = _parse_mistral_pages(body)
            set_safe_span_attributes(
                span,
                {
                    "llm.status": "ok",
                    "llm.latency_ms": latency_ms,
                    "media.page_count": page_count,
                    "media.page_count_requested": page_count_requested,
                },
            )
            return MediaResult(
                text=text,
                provider_id=provider_id,
                model=request.model,
                latency_ms=latency_ms,
                input_tokens=0,
                output_tokens=0,
                page_count=page_count,
                image_count=0,
                metadata={"transport": "mistral_ocr"},
            )
    finally:
        if owned:
            http.close()
