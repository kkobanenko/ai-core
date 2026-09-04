"""AU01B: capability + single-provider vision/OCR (mocked HTTP, no live calls)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from ai_core.capabilities import (
    ProviderCapability,
    get_model_profile,
    model_has_capability,
    require_model_capability,
)
from ai_core.media import MediaResult, OcrPdfRequest, VisionImageRequest
from ai_core.media_errors import MediaAuthError, MediaTransportError
from ai_core.media_gate import MediaPrivacyError, assert_media_allowed
from ai_core.ocr_pdf import build_mistral_ocr_payload, invoke_pdf_ocr
from ai_core.privacy import DataClass, OutboundForm
from ai_core.provider_catalog import PROVIDER_GPU_OLLAMA, PROVIDER_MISTRAL_EXTERNAL
from ai_core.resolve import resolve_provider_endpoint
from ai_core.vision import build_ollama_vision_payload, invoke_vision


def test_qwen25vl_has_vision_image():
    assert model_has_capability(PROVIDER_GPU_OLLAMA, "qwen2.5vl:7b", ProviderCapability.VISION_IMAGE)


def test_qwen35_not_automatically_vision():
    assert not model_has_capability(PROVIDER_GPU_OLLAMA, "qwen3.5:9b", ProviderCapability.VISION_IMAGE)
    profile = get_model_profile(PROVIDER_GPU_OLLAMA, "qwen3.5:9b")
    assert profile is not None
    assert ProviderCapability.VISION_IMAGE not in profile.capabilities


def test_mistral_ocr_latest_has_ocr_pdf():
    assert model_has_capability(
        PROVIDER_MISTRAL_EXTERNAL, "mistral-ocr-latest", ProviderCapability.OCR_PDF
    )


def test_ministral_not_automatically_ocr_pdf():
    assert not model_has_capability(
        PROVIDER_MISTRAL_EXTERNAL, "ministral-8b-2512", ProviderCapability.OCR_PDF
    )


def test_unknown_model_not_assumed_multimodal():
    assert get_model_profile(PROVIDER_GPU_OLLAMA, "totally-unknown:99b") is None
    assert not model_has_capability(
        PROVIDER_GPU_OLLAMA, "totally-unknown:99b", ProviderCapability.VISION_IMAGE
    )
    with pytest.raises(ValueError, match="Unknown model"):
        require_model_capability(
            PROVIDER_GPU_OLLAMA, "totally-unknown:99b", ProviderCapability.VISION_IMAGE
        )


def test_ollama_vision_payload_shape():
    payload = build_ollama_vision_payload(
        model="qwen2.5vl:7b",
        prompt="extract",
        image_base64_list=["aaa", "bbb"],
    )
    assert payload == {
        "model": "qwen2.5vl:7b",
        "prompt": "extract",
        "images": ["aaa", "bbb"],
        "stream": False,
    }


class _FakeResponse:
    def __init__(self, status_code: int, body: dict[str, Any] | None = None):
        self.status_code = status_code
        self._body = body or {}

    def json(self) -> dict[str, Any]:
        return self._body


class _CountingClient:
    """Подмена httpx.Client: считает POST и возвращает заранее заданный ответ/ошибку."""

    def __init__(self, handler):
        self.handler = handler
        self.posts = 0
        self.last_url = None
        self.last_json = None
        self.last_headers = None

    def post(self, url, json=None, headers=None, timeout=None):
        self.posts += 1
        self.last_url = url
        self.last_json = json
        self.last_headers = headers
        return self.handler(url, json, headers, timeout)

    def close(self):
        return None


def test_invoke_vision_one_upstream_call(monkeypatch):
    monkeypatch.setenv("LOCAL_GPU_OLLAMA_BASE_URL", "http://gpu-ollama.test:11434")

    def handler(url, json_body, headers, timeout):
        assert url.endswith("/api/generate")
        assert json_body["model"] == "qwen2.5vl:7b"
        assert json_body["images"] == ["aGVsbG8="]  # b"hello"
        return _FakeResponse(
            200,
            {
                "response": "page text",
                "prompt_eval_count": 11,
                "eval_count": 3,
            },
        )

    client = _CountingClient(handler)
    result = invoke_vision(
        VisionImageRequest(
            model="qwen2.5vl:7b",
            images=(b"hello",),
            prompt="read",
            timeout_seconds=30,
        ),
        data_class=DataClass.SYNTHETIC,
        outbound_form=OutboundForm.RAW,
        client=client,
    )
    assert client.posts == 1
    assert isinstance(result, MediaResult)
    assert result.text == "page text"
    assert result.provider_id == PROVIDER_GPU_OLLAMA
    assert result.input_tokens == 11
    assert result.image_count == 1


def test_mistral_ocr_payload_and_one_call(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-fake-key-not-real")
    monkeypatch.setenv("MISTRAL_API_BASE", "https://api.mistral.ai/v1")

    pdf = b"%PDF-1.4 fake"
    payload = build_mistral_ocr_payload(model="mistral-ocr-latest", pdf_bytes=pdf, max_pages=3)
    assert payload["model"] == "mistral-ocr-latest"
    assert payload["pages"] == "0-2"
    assert payload["document"]["type"] == "document_url"
    assert "base64," in payload["document"]["document_url"]

    def handler(url, json_body, headers, timeout):
        assert url.endswith("/ocr")
        assert "Authorization" in (headers or {})
        assert "test-fake-key-not-real" not in json.dumps(json_body)
        return _FakeResponse(
            200,
            {
                "pages": [{"markdown": "hello md"}],
                "usage_info": {"pages_processed": 1},
            },
        )

    client = _CountingClient(handler)
    result = invoke_pdf_ocr(
        OcrPdfRequest(model="mistral-ocr-latest", pdf_bytes=pdf, max_pages=3),
        data_class=DataClass.PUBLIC_NO_PII,
        outbound_form=OutboundForm.SANITIZED,
        client=client,
    )
    assert client.posts == 1
    assert result.text == "hello md"
    assert result.page_count == 1
    assert result.provider_id == PROVIDER_MISTRAL_EXTERNAL


@pytest.mark.parametrize(
    "exc,category",
    [
        (httpx.TimeoutException("slow"), "timeout"),
        (httpx.ConnectError("down"), "connection"),
    ],
)
def test_vision_timeout_and_connection_normalized(monkeypatch, exc, category):
    monkeypatch.setenv("LOCAL_GPU_OLLAMA_BASE_URL", "http://gpu-ollama.test:11434")

    def handler(*_a, **_k):
        raise exc

    client = _CountingClient(handler)
    with pytest.raises(MediaTransportError) as info:
        invoke_vision(
            VisionImageRequest(model="qwen2.5vl:7b", images=(b"x",), prompt="p"),
            data_class=DataClass.SYNTHETIC,
            client=client,
        )
    assert info.value.category == category
    assert client.posts == 1
    # fallback-eligible marker
    assert isinstance(info.value, MediaTransportError)


def test_vision_429_and_5xx(monkeypatch):
    monkeypatch.setenv("LOCAL_GPU_OLLAMA_BASE_URL", "http://gpu-ollama.test:11434")

    for code, cat in ((429, "http_429"), (503, "http_5xx")):
        client = _CountingClient(lambda *a, code=code, **k: _FakeResponse(code))
        with pytest.raises(MediaTransportError) as info:
            invoke_vision(
                VisionImageRequest(model="qwen2.5vl:7b", images=(b"x",), prompt="p"),
                data_class=DataClass.SYNTHETIC,
                client=client,
            )
        assert info.value.category == cat
        assert info.value.status_code == code
        assert client.posts == 1


def test_vision_401_terminal(monkeypatch):
    monkeypatch.setenv("LOCAL_GPU_OLLAMA_BASE_URL", "http://gpu-ollama.test:11434")
    client = _CountingClient(lambda *a, **k: _FakeResponse(401))
    with pytest.raises(MediaAuthError) as info:
        invoke_vision(
            VisionImageRequest(model="qwen2.5vl:7b", images=(b"x",), prompt="p"),
            data_class=DataClass.SYNTHETIC,
            client=client,
        )
    assert info.value.status_code == 401
    assert not isinstance(info.value, MediaTransportError)


def test_secret_absent_from_exception_and_repr(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "super-secret-key-VALUE-xyz")
    monkeypatch.setenv("MISTRAL_API_BASE", "https://api.mistral.ai/v1")
    endpoint = resolve_provider_endpoint(PROVIDER_MISTRAL_EXTERNAL)
    assert "super-secret-key-VALUE-xyz" not in repr(endpoint)
    assert "super-secret-key-VALUE-xyz" not in str(endpoint)

    client = _CountingClient(lambda *a, **k: _FakeResponse(401, {}))
    with pytest.raises(MediaAuthError) as info:
        invoke_pdf_ocr(
            OcrPdfRequest(model="mistral-ocr-latest", pdf_bytes=b"%PDF"),
            data_class=DataClass.PUBLIC_NO_PII,
            outbound_form=OutboundForm.SANITIZED,
            client=client,
        )
    assert "super-secret-key-VALUE-xyz" not in str(info.value)
    assert "super-secret-key-VALUE-xyz" not in repr(info.value)


def test_privacy_blocks_raw_external_mistral():
    with pytest.raises(MediaPrivacyError):
        assert_media_allowed(
            provider_id=PROVIDER_MISTRAL_EXTERNAL,
            model="mistral-ocr-latest",
            capability=ProviderCapability.OCR_PDF,
            data_class=DataClass.PRIVATE_CLIENT_DATA,
            outbound_form=OutboundForm.RAW,
        )


def test_privacy_and_capability_both_required(monkeypatch):
    # Capability fails first for wrong model even if privacy would allow synthetic.
    with pytest.raises(ValueError, match="lacks capability"):
        assert_media_allowed(
            provider_id=PROVIDER_MISTRAL_EXTERNAL,
            model="ministral-8b-2512",
            capability=ProviderCapability.OCR_PDF,
            data_class=DataClass.SYNTHETIC,
            outbound_form=OutboundForm.RAW,
        )
    # Privacy fails for raw sensitive on mistral even with right model.
    with pytest.raises(MediaPrivacyError):
        invoke_pdf_ocr(
            OcrPdfRequest(model="mistral-ocr-latest", pdf_bytes=b"%PDF"),
            data_class=DataClass.PRIVATE_CLIENT_DATA,
            outbound_form=OutboundForm.RAW,
            client=_CountingClient(lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call"))),
        )


def test_traces_omit_media_by_default(monkeypatch):
    """При default PHOENIX_TRACE_INCLUDE_IO=false span attrs без сырых байт."""
    monkeypatch.setenv("LOCAL_GPU_OLLAMA_BASE_URL", "http://gpu-ollama.test:11434")
    monkeypatch.delenv("PHOENIX_TRACE_INCLUDE_IO", raising=False)
    recorded: list[dict[str, Any]] = []

    class FakeSpan:
        def set_attribute(self, key, value):
            recorded.append({key: value})

    class CM:
        def __enter__(self):
            return FakeSpan()

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("ai_core.vision.start_llm_span", lambda **kw: CM())
    client = _CountingClient(
        lambda *a, **k: _FakeResponse(200, {"response": "t", "prompt_eval_count": 1, "eval_count": 1})
    )
    invoke_vision(
        VisionImageRequest(model="qwen2.5vl:7b", images=(b"\xff\xd8secretbytes",), prompt="p"),
        data_class=DataClass.SYNTHETIC,
        client=client,
    )
    blob = json.dumps(recorded)
    assert "secretbytes" not in blob
    assert "\\xff\\xd8" not in blob


def test_no_nested_fallback_api_exported():
    import ai_core

    for name in (
        "invoke_with_fallback",
        "ocr_provider_chain",
        "try_providers_until_success",
        "run_model_chain",
    ):
        assert not hasattr(ai_core, name)


def test_supports_multimodal_profile_unchanged():
    from ai_core.provider_catalog import get_provider_profile

    assert get_provider_profile(PROVIDER_GPU_OLLAMA).supports_multimodal is False
    assert get_provider_profile(PROVIDER_MISTRAL_EXTERNAL).supports_multimodal is False
