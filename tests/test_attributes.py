from ai_core.attributes import sanitize_attributes


def test_sanitize_attributes_keeps_allowlist_and_drops_sensitive_keys():
    result = sanitize_attributes(
        {
            "workflow": "chat",
            "adapter": "langchain",
            "provider_id": "local_gpu_ollama",
            "latency_ms": 123,
            "email": "planner@example.com",
            "jwt": "secret-token",
        }
    )
    assert result == {
        "workflow": "chat",
        "adapter": "langchain",
        "provider_id": "local_gpu_ollama",
        "latency_ms": 123,
    }


def test_sanitize_attributes_drops_non_scalar_values():
    assert sanitize_attributes({"workflow": ["chat"]}) == {}
