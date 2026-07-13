"""Общая библиотека Phoenix tracing и IO-политики для AI-проектов."""

from ai_core.config import PhoenixConfig, load_phoenix_config
from ai_core.io_policy import maybe_truncate

__all__ = [
    "PhoenixConfig",
    "load_phoenix_config",
    "maybe_truncate",
]
