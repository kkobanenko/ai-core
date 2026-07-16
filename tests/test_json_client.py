import httpx
import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from ai_core.json_client import LangChainJsonClient
from ai_core.models import ProviderConfig


def cfg(name: str) -> ProviderConfig:
    return ProviderConfig(name, "ollama_native", f"{name}-model", "http://x", "", True, 10.0)


def test_transport_error_falls_back(monkeypatch):
    models = {
        "primary": RunnableLambda(lambda _: (_ for _ in ()).throw(httpx.ConnectError("down"))),
        "fallback": RunnableLambda(
            lambda _: AIMessage(
                content='{"items": []}',
                usage_metadata={"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
            )
        ),
    }
    monkeypatch.setattr("ai_core.json_client.build_chat_model", lambda spec: models[spec.name])
    client = LangChainJsonClient((cfg("primary"), cfg("fallback")))
    result = client.create_json_completion("system", "user")
    assert result.provider_name == "fallback"
    assert result.raw_content == '{"items": []}'
    assert [x["outcome"] for x in result.attempt_summary] == ["transport_error", "success"]


def test_value_error_is_terminal(monkeypatch):
    model = RunnableLambda(lambda _: (_ for _ in ()).throw(ValueError("bad schema")))
    monkeypatch.setattr("ai_core.json_client.build_chat_model", lambda _: model)
    client = LangChainJsonClient((cfg("primary"), cfg("fallback")))
    with pytest.raises(ValueError, match="bad schema"):
        client.create_json_completion("system", "user")


class HttpFailure(RuntimeError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}")


@pytest.mark.parametrize("status_code", [429, 503])
def test_retryable_http_status_falls_back(monkeypatch, status_code):
    def build(spec):
        if spec.name == "primary":
            return RunnableLambda(lambda _: (_ for _ in ()).throw(HttpFailure(status_code)))
        return RunnableLambda(lambda _: AIMessage(content='{"items": []}'))

    monkeypatch.setattr("ai_core.json_client.build_chat_model", build)
    result = LangChainJsonClient((cfg("primary"), cfg("fallback"))).create_json_completion("s", "u")
    assert result.provider_name == "fallback"


def test_malformed_success_does_not_fall_back(monkeypatch):
    build_calls = []

    def build(spec):
        build_calls.append(spec.name)
        return RunnableLambda(lambda _: AIMessage(content="not-json"))

    monkeypatch.setattr("ai_core.json_client.build_chat_model", build)
    result = LangChainJsonClient((cfg("primary"), cfg("fallback"))).create_json_completion("s", "u")
    assert result.raw_content == "not-json"
    assert result.provider_name == "primary"
    assert build_calls == ["primary", "fallback"]
    assert [row["outcome"] for row in result.attempt_summary] == ["success"]
