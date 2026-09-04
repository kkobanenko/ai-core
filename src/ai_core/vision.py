"""Single-provider Ollama vision: ровно один HTTP POST на invoke_vision."""

from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from ai_core.capabilities import ProviderCapability
from ai_core.media import MediaResult, VisionImageRequest
from ai_core.media_errors import MediaTransportError, classify_http_error
from ai_core.media_gate import assert_media_allowed
from ai_core.privacy import DataClass, OutboundForm
from ai_core.provider_catalog import PROVIDER_GPU_OLLAMA
from ai_core.resolve import resolve_provider_endpoint
from ai_core.tracing import start_llm_span


def _normalize_images(images: tuple[bytes | str, ...]) -> list[str]:
    """bytes → base64; str считаем уже base64."""
    out: list[str] = []
    for item in images:
        if isinstance(item, bytes):
            out.append(base64.b64encode(item).decode("ascii"))
        else:
            text = str(item).strip()
            if not text:
                raise ValueError("empty image entry")
            out.append(text)
    if not out:
        raise ValueError("images is empty")
    return out


def build_ollama_vision_payload(
    *,
    model: str,
    prompt: str,
    image_base64_list: list[str],
) -> dict[str, Any]:
    """Payload совместим с proven Prozakupki Ollama vision (/api/generate)."""
    return {
        "model": model,
        "prompt": prompt,
        "images": image_base64_list,
        "stream": False,
    }


def invoke_vision(
    request: VisionImageRequest,
    *,
    provider_id: str = PROVIDER_GPU_OLLAMA,
    data_class: DataClass = DataClass.PUBLIC_NO_PII,
    outbound_form: OutboundForm = OutboundForm.RAW,
    client: httpx.Client | None = None,
) -> MediaResult:
    """Один upstream-вызов Ollama vision. Без retry/fallback/другого провайдера."""
    assert_media_allowed(
        provider_id=provider_id,
        model=request.model,
        capability=ProviderCapability.VISION_IMAGE,
        data_class=data_class,
        outbound_form=outbound_form,
    )
    endpoint = resolve_provider_endpoint(provider_id)
    if not endpoint.base_url:
        raise ValueError(
            f"Missing base URL for {provider_id}: set one of LOCAL_GPU_OLLAMA_HOST / "
            "LOCAL_GPU_OLLAMA_BASE_URL / LOCAL_GPU_OLLAMA_URL"
        )

    images_b64 = _normalize_images(request.images)
    payload = build_ollama_vision_payload(
        model=request.model,
        prompt=request.prompt,
        image_base64_list=images_b64,
    )
    url = f"{endpoint.base_url.rstrip('/')}/api/generate"
    headers: dict[str, str] = {}
    if endpoint.api_key:
        headers["Authorization"] = f"Bearer {endpoint.api_key}"

    owned = client is None
    http = client or httpx.Client()
    started = time.perf_counter()
    attrs = {
        "provider": provider_id,
        "model": request.model,
        "capability": ProviderCapability.VISION_IMAGE.value,
        "image_count": len(images_b64),
    }
    try:
        with start_llm_span(workflow="ai_core.invoke_vision", attributes=attrs) as span:
            try:
                # Ровно один POST — инвариант WP.
                response = http.post(
                    url,
                    json=payload,
                    headers=headers or None,
                    timeout=request.timeout_seconds,
                )
            except httpx.TimeoutException as exc:
                raise MediaTransportError(
                    "ollama vision timeout",
                    category="timeout",
                ) from exc
            except httpx.TransportError as exc:
                raise MediaTransportError(
                    f"ollama vision transport error: {exc.__class__.__name__}",
                    category="connection",
                ) from exc

            if response.status_code >= 400:
                raise classify_http_error(response.status_code, f"ollama vision HTTP {response.status_code}")

            body = response.json()
            latency_ms = int((time.perf_counter() - started) * 1000)
            text = str(body.get("response") or "").strip()
            input_tokens = int(body.get("prompt_eval_count") or 0)
            output_tokens = int(body.get("eval_count") or 0)
            if span is not None:
                try:
                    span.set_attribute("status", "ok")
                    span.set_attribute("latency_ms", latency_ms)
                    span.set_attribute("input_tokens", input_tokens)
                    span.set_attribute("output_tokens", output_tokens)
                except Exception:
                    pass
            return MediaResult(
                text=text,
                provider_id=provider_id,
                model=request.model,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                page_count=0,
                image_count=len(images_b64),
                metadata={"transport": "ollama_generate"},
            )
    finally:
        if owned:
            http.close()
