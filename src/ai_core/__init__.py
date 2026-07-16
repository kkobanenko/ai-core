"""Общая библиотека Phoenix tracing и IO-политики для AI-проектов."""

from ai_core.config import PhoenixConfig, load_phoenix_config
from ai_core.io_policy import maybe_truncate
from ai_core.json_client import LangChainJsonClient, ProviderTransportError
from ai_core.models import AttemptRecord, JsonCompletion, ProviderConfig
from ai_core.provider_factory import build_chat_model
from ai_core.tracing import init_tracing, shutdown_tracing, start_llm_span

__all__ = [
    "AttemptRecord",
    "build_chat_model",
    "JsonCompletion",
    "LangChainJsonClient",
    "PhoenixConfig",
    "ProviderConfig",
    "ProviderTransportError",
    "load_phoenix_config",
    "init_tracing",
    "maybe_truncate",
    "shutdown_tracing",
    "start_llm_span",
]
