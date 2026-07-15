from ai_core.safe_attributes import sanitize_span_attributes


def test_sanitize_span_attributes_keeps_allowlisted_scalars():
    attrs = sanitize_span_attributes({
        "workflow": "classify",
        "llm.provider": "local_gpu_ollama",
        "llm.model": "qwen3.6:35b",
        "llm.latency_ms": 120,
        "source_card_id": 42,
    })
    assert attrs == {
        "workflow": "classify",
        "llm.provider": "local_gpu_ollama",
        "llm.model": "qwen3.6:35b",
        "llm.latency_ms": 120,
        "source_card_id": 42,
    }


def test_sanitize_span_attributes_drops_unknown_and_complex_values():
    attrs = sanitize_span_attributes({
        "api_key": "secret",
        "prompt": "private text",
        "llm.model": {"nested": "bad"},
    })
    assert attrs == {}
