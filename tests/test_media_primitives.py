"""AU01B / AU01B1: capability + single-provider vision/OCR (mocked HTTP)."""

from __future__ import annotations

import inspect
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
from ai_core.provider_catalog import (
    CANONICAL_PROVIDER_IDS,
    PROVIDER_GPU_OLLAMA,
    PROVIDER_MISTRAL_EXTERNAL,
    PROVIDER_OLLAMA_CLOUD,
    PROVIDER_VM100_LOCAL_OLLAMA,
    get_provider_profile,
)
from ai_core.resolve import resolve_provider_endpoint
from ai_core.safe_attributes import SAFE_ATTRIBUTE_KEYS, sanitize_span_attributes, set_safe_span_attributes
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
        outbound_form=OutboundForm.RAW,
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
            outbound_form=OutboundForm.RAW,
            client=client,
        )
    assert info.value.category == category
    assert client.posts == 1
    assert isinstance(info.value, MediaTransportError)


def test_vision_429_and_5xx(monkeypatch):
    monkeypatch.setenv("LOCAL_GPU_OLLAMA_BASE_URL", "http://gpu-ollama.test:11434")

    for code, cat in ((429, "http_429"), (503, "http_5xx")):
        client = _CountingClient(lambda *a, code=code, **k: _FakeResponse(code))
        with pytest.raises(MediaTransportError) as info:
            invoke_vision(
                VisionImageRequest(model="qwen2.5vl:7b", images=(b"x",), prompt="p"),
                data_class=DataClass.SYNTHETIC,
                outbound_form=OutboundForm.RAW,
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
            outbound_form=OutboundForm.RAW,
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
            outbound_form=OutboundForm.RAW,
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
    with pytest.raises(ValueError, match="lacks capability"):
        assert_media_allowed(
            provider_id=PROVIDER_MISTRAL_EXTERNAL,
            model="ministral-8b-2512",
            capability=ProviderCapability.OCR_PDF,
            data_class=DataClass.SYNTHETIC,
            outbound_form=OutboundForm.RAW,
        )
    with pytest.raises(MediaPrivacyError):
        invoke_pdf_ocr(
            OcrPdfRequest(model="mistral-ocr-latest", pdf_bytes=b"%PDF"),
            data_class=DataClass.PRIVATE_CLIENT_DATA,
            outbound_form=OutboundForm.RAW,
            client=_CountingClient(lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call"))),
        )


def test_media_result_repr_content_free():
    secret_text = "PERSON SECRET 123456789"
    result = MediaResult(
        text=secret_text,
        provider_id=PROVIDER_GPU_OLLAMA,
        model="qwen2.5vl:7b",
        latency_ms=12,
        page_count=0,
        image_count=1,
    )
    blob = repr(result)
    assert "PERSON" not in blob
    assert "SECRET" not in blob
    assert "123456789" not in blob
    assert "chars=" in blob
    assert "provider_id=" in blob


def test_privacy_args_required_vision_no_http():
    client = _CountingClient(lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call")))
    req = VisionImageRequest(model="qwen2.5vl:7b", images=(b"x",), prompt="p")
    with pytest.raises(TypeError):
        invoke_vision(req, outbound_form=OutboundForm.RAW, client=client)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        invoke_vision(req, data_class=DataClass.SYNTHETIC, client=client)  # type: ignore[call-arg]
    assert client.posts == 0
    sig = inspect.signature(invoke_vision)
    assert sig.parameters["data_class"].default is inspect.Parameter.empty
    assert sig.parameters["outbound_form"].default is inspect.Parameter.empty


def test_privacy_args_required_ocr_no_http():
    client = _CountingClient(lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call")))
    req = OcrPdfRequest(model="mistral-ocr-latest", pdf_bytes=b"%PDF")
    with pytest.raises(TypeError):
        invoke_pdf_ocr(req, outbound_form=OutboundForm.RAW, client=client)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        invoke_pdf_ocr(req, data_class=DataClass.PUBLIC_NO_PII, client=client)  # type: ignore[call-arg]
    assert client.posts == 0
    sig = inspect.signature(invoke_pdf_ocr)
    assert sig.parameters["data_class"].default is inspect.Parameter.empty
    assert sig.parameters["outbound_form"].default is inspect.Parameter.empty


def test_raw_bytes_use_outbound_form_raw_not_sanitized_by_base64(monkeypatch):
    """Неизменённые PDF bytes → consumer обязан передать RAW; base64 ≠ sanitization."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-fake-key-not-real")
    client = _CountingClient(
        lambda *a, **k: _FakeResponse(200, {"pages": [{"markdown": "x"}], "usage_info": {"pages_processed": 1}})
    )
    # Explicit RAW for unchanged bytes — valid path.
    invoke_pdf_ocr(
        OcrPdfRequest(model="mistral-ocr-latest", pdf_bytes=b"%PDF-raw"),
        data_class=DataClass.PUBLIC_NO_PII,
        outbound_form=OutboundForm.RAW,
        client=client,
    )
    assert client.posts == 1
    # SANITIZED without prior consumer sanitization is a consumer policy mistake;
    # ai-core still accepts the flag but wire still carries original bytes encoding.
    payload = build_mistral_ocr_payload(
        model="mistral-ocr-latest", pdf_bytes=b"%PDF-raw", max_pages=1
    )
    assert "base64," in payload["document"]["document_url"]


def test_tracing_namespaced_safe_attrs_and_no_bypass(monkeypatch):
    monkeypatch.setenv("LOCAL_GPU_OLLAMA_BASE_URL", "http://gpu-ollama.test:11434")
    monkeypatch.delenv("PHOENIX_TRACE_INCLUDE_IO", raising=False)

    span_attrs: dict[str, Any] = {}
    start_attrs: dict[str, Any] = {}

    class FakeSpan:
        def set_attribute(self, key, value):
            span_attrs[key] = value

    class CM:
        def __enter__(self):
            return FakeSpan()

        def __exit__(self, *a):
            return False

    def fake_start_llm_span(*, workflow, attributes=None, **_kw):
        start_attrs.clear()
        start_attrs.update(attributes or {})
        start_attrs["workflow"] = workflow
        # Проверяем реальную семантику sanitizer на входных attrs.
        for key, value in sanitize_span_attributes(start_attrs).items():
            span_attrs[key] = value
        return CM()

    monkeypatch.setattr("ai_core.vision.start_llm_span", fake_start_llm_span)

    ocr_secret = "OCR FULL OUTPUT PERSON SECRET"
    client = _CountingClient(
        lambda *a, **k: _FakeResponse(
            200,
            {"response": ocr_secret, "prompt_eval_count": 2, "eval_count": 4},
        )
    )
    invoke_vision(
        VisionImageRequest(
            model="qwen2.5vl:7b",
            images=(b"\xff\xd8secretbytes",),
            prompt="p",
        ),
        data_class=DataClass.SYNTHETIC,
        outbound_form=OutboundForm.RAW,
        client=client,
    )

    assert span_attrs.get("llm.provider") == PROVIDER_GPU_OLLAMA
    assert span_attrs.get("llm.model") == "qwen2.5vl:7b"
    assert span_attrs.get("ai.capability") == ProviderCapability.VISION_IMAGE.value
    assert "llm.latency_ms" in span_attrs
    assert span_attrs.get("media.image_count") == 1
    assert "provider" not in span_attrs
    assert "model" not in span_attrs
    assert "latency_ms" not in span_attrs

    # Unnamespaced / secrets rejected by allowlist.
    assert sanitize_span_attributes({"provider": "x", "api_key": "k", "arbitrary": 1}) == {}
    assert "provider" not in SAFE_ATTRIBUTE_KEYS

    blob = json.dumps(span_attrs)
    assert "secretbytes" not in blob
    assert ocr_secret not in blob
    assert "PERSON" not in blob
    assert "API_KEY" not in blob


def test_set_safe_span_attributes_uses_shared_sanitizer():
    recorded: dict[str, Any] = {}

    class FakeSpan:
        def set_attribute(self, key, value):
            recorded[key] = value

    set_safe_span_attributes(
        FakeSpan(),
        {
            "llm.provider": "gpu_ollama",
            "llm.model": "qwen2.5vl:7b",
            "ai.capability": "vision_image",
            "llm.latency_ms": 9,
            "media.page_count": 2,
            "media.image_count": 1,
            "provider": "dropped",
            "api_key": "secret-key-value",
            "response": "OCR FULL TEXT",
        },
    )
    assert recorded == {
        "llm.provider": "gpu_ollama",
        "llm.model": "qwen2.5vl:7b",
        "ai.capability": "vision_image",
        "llm.latency_ms": 9,
        "media.page_count": 2,
        "media.image_count": 1,
    }
    assert "secret-key-value" not in repr(recorded)
    assert "OCR FULL TEXT" not in recorded.values()


def test_ocr_tracing_page_count_namespaced(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-fake-key-not-real")
    span_attrs: dict[str, Any] = {}

    class FakeSpan:
        def set_attribute(self, key, value):
            span_attrs[key] = value

    class CM:
        def __enter__(self):
            return FakeSpan()

        def __exit__(self, *a):
            return False

    def fake_start(*, workflow, attributes=None, **_kw):
        for key, value in sanitize_span_attributes({**(attributes or {}), "workflow": workflow}).items():
            span_attrs[key] = value
        return CM()

    monkeypatch.setattr("ai_core.ocr_pdf.start_llm_span", fake_start)
    client = _CountingClient(
        lambda *a, **k: _FakeResponse(
            200,
            {"pages": [{"markdown": "SENSITIVE OCR BODY"}], "usage_info": {"pages_processed": 3}},
        )
    )
    invoke_pdf_ocr(
        OcrPdfRequest(model="mistral-ocr-latest", pdf_bytes=b"%PDF-bytes-secret", max_pages=5),
        data_class=DataClass.PUBLIC_NO_PII,
        outbound_form=OutboundForm.RAW,
        client=client,
    )
    assert span_attrs.get("llm.provider") == PROVIDER_MISTRAL_EXTERNAL
    assert span_attrs.get("media.page_count") == 3
    assert span_attrs.get("media.page_count_requested") == 5
    blob = json.dumps(span_attrs)
    assert "SENSITIVE OCR BODY" not in blob
    assert "PDF-bytes-secret" not in blob
    assert "test-fake-key-not-real" not in blob


def test_explicit_api_key_optional_policy():
    assert get_provider_profile(PROVIDER_VM100_LOCAL_OLLAMA).api_key_optional is True
    assert get_provider_profile(PROVIDER_GPU_OLLAMA).api_key_optional is True
    assert get_provider_profile(PROVIDER_OLLAMA_CLOUD).api_key_optional is False
    assert get_provider_profile(PROVIDER_MISTRAL_EXTERNAL).api_key_optional is False
    assert "AI_PROVIDER" not in get_provider_profile(PROVIDER_OLLAMA_CLOUD).credential_env_keys


def test_ai_provider_not_used_as_credential(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "ollama_cloud")
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    endpoint = resolve_provider_endpoint(PROVIDER_OLLAMA_CLOUD)
    assert endpoint.api_key == ""
    assert endpoint.api_key_optional is False
    assert "ollama_cloud" not in repr(endpoint) or endpoint.provider_id == PROVIDER_OLLAMA_CLOUD
    assert "ollama_cloud" != endpoint.api_key


def test_resolve_all_canonical_providers_explicit_metadata(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://local.test:11434")
    monkeypatch.setenv("LOCAL_GPU_OLLAMA_BASE_URL", "http://gpu.test:11434")
    monkeypatch.setenv("MISTRAL_API_KEY", "mistral-test-key")
    monkeypatch.setenv("MISTRAL_API_BASE", "https://api.mistral.ai/v1")
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)

    expected_optional = {
        PROVIDER_VM100_LOCAL_OLLAMA: True,
        PROVIDER_OLLAMA_CLOUD: False,
        PROVIDER_GPU_OLLAMA: True,
        PROVIDER_MISTRAL_EXTERNAL: False,
    }
    for pid in CANONICAL_PROVIDER_IDS:
        ep = resolve_provider_endpoint(pid)
        assert ep.provider_id == pid
        assert ep.api_key_optional is expected_optional[pid]
        assert ep.api_key_optional is get_provider_profile(pid).api_key_optional
        assert "mistral-test-key" not in repr(ep)

    # Нет name-heuristics по provider_id в resolve.py
    import ai_core.resolve as resolve_mod
    import inspect as _inspect

    src = _inspect.getsource(resolve_mod)
    assert 'endswith("ollama")' not in src
    assert "provider_id.endswith" not in src
    assert "if provider_id ==" not in src


@pytest.mark.parametrize(
    "bad",
    ["/tmp/page.png", "https://example.test/page.png", "abc"],
)
def test_str_image_rejected_before_network(bad, monkeypatch):
    monkeypatch.setenv("LOCAL_GPU_OLLAMA_BASE_URL", "http://gpu-ollama.test:11434")
    client = _CountingClient(lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call")))
    with pytest.raises(TypeError):
        invoke_vision(
            VisionImageRequest(model="qwen2.5vl:7b", images=(bad,), prompt="p"),  # type: ignore[arg-type]
            data_class=DataClass.SYNTHETIC,
            outbound_form=OutboundForm.RAW,
            client=client,
        )
    assert client.posts == 0


def test_bytes_image_still_works(monkeypatch):
    monkeypatch.setenv("LOCAL_GPU_OLLAMA_BASE_URL", "http://gpu-ollama.test:11434")
    client = _CountingClient(
        lambda *a, **k: _FakeResponse(200, {"response": "ok", "prompt_eval_count": 1, "eval_count": 1})
    )
    result = invoke_vision(
        VisionImageRequest(model="qwen2.5vl:7b", images=(b"\x89PNG",), prompt="p"),
        data_class=DataClass.SYNTHETIC,
        outbound_form=OutboundForm.RAW,
        client=client,
    )
    assert client.posts == 1
    assert result.image_count == 1


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
    assert get_provider_profile(PROVIDER_GPU_OLLAMA).supports_multimodal is False
    assert get_provider_profile(PROVIDER_MISTRAL_EXTERNAL).supports_multimodal is False
