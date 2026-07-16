from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from ai_core.models import ProviderConfig


def build_chat_model(config: ProviderConfig) -> BaseChatModel:
    if not config.is_ready():
        raise ValueError(f"Provider not ready: {config.name}")
    if config.transport == "ollama_native":
        from langchain_ollama import ChatOllama

        kwargs = {
            "model": config.model,
            "base_url": config.base_url.rstrip("/"),
            "temperature": 0,
            "validate_model_on_init": False,
            "client_kwargs": {"timeout": config.timeout_seconds},
        }
        if config.headers:
            kwargs["client_kwargs"]["headers"] = config.headers
        return ChatOllama(**kwargs)
    if config.name == "mistral":
        from langchain_mistralai import ChatMistralAI

        return ChatMistralAI(
            model=config.model,
            api_key=config.api_key,
            endpoint=config.base_url.rstrip("/"),
            temperature=0,
            timeout=config.timeout_seconds,
            max_retries=0,
        )
    if config.transport == "openai_compatible":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url or None,
            temperature=0,
            timeout=config.timeout_seconds,
            max_retries=0,
        )
    raise ValueError(f"Unsupported provider transport: {config.name}/{config.transport}")
