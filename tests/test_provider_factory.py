from unittest.mock import patch

from ai_core.models import ProviderConfig
from ai_core.provider_factory import build_chat_model


def test_local_gpu_ollama_maps_to_chat_ollama():
    cfg = ProviderConfig(
        name="local_gpu_ollama",
        transport="ollama_native",
        model="qwen3.6:35b",
        base_url="http://100.91.166.5:11434",
        api_key="",
        api_key_optional=True,
        timeout_seconds=600.0,
    )
    with patch("langchain_ollama.ChatOllama") as constructor:
        build_chat_model(cfg)
    constructor.assert_called_once_with(
        model="qwen3.6:35b",
        base_url="http://100.91.166.5:11434",
        temperature=0,
        validate_model_on_init=False,
        client_kwargs={"timeout": 600.0},
    )


def test_mistral_maps_to_chat_mistral():
    cfg = ProviderConfig(
        name="mistral",
        transport="openai_compatible",
        model="mistral-small-latest",
        base_url="https://api.mistral.ai/v1",
        api_key="key",
        api_key_optional=False,
        timeout_seconds=120.0,
    )
    with patch("langchain_mistralai.ChatMistralAI") as constructor:
        build_chat_model(cfg)
    assert constructor.call_args.kwargs["model"] == "mistral-small-latest"
