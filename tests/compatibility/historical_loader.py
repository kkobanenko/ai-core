"""Isolated execution harness for pinned v0.2.0 compatibility evidence."""

from __future__ import annotations

from types import ModuleType, SimpleNamespace
from typing import Any
import sys

from tests.compatibility.git_ref import read_blob


_MODULE_NAMES = (
    "ai_core",
    "ai_core.models",
    "ai_core.provider_factory",
    "httpx",
    "langchain_core",
    "langchain_core.messages",
    "langchain_core.runnables",
)
_MISSING = object()


class _Message:
    def __init__(
        self,
        content: str,
        *,
        model_name: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        self.content = content
        self.response_metadata = (
            {} if model_name is None else {"model_name": model_name}
        )
        self.usage_metadata = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }


class _RunnableLambda:
    def __init__(self, function: Any) -> None:
        self._function = function

    def invoke(self, value: object) -> object:
        return self._function(value)

    def with_fallbacks(
        self,
        fallbacks: list["_RunnableLambda"],
        *,
        exceptions_to_handle: tuple[type[BaseException], ...],
    ) -> "_FallbackRunnable":
        return _FallbackRunnable([self, *fallbacks], exceptions_to_handle)


class _FallbackRunnable:
    def __init__(
        self,
        branches: list[_RunnableLambda],
        exceptions_to_handle: tuple[type[BaseException], ...],
    ) -> None:
        self._branches = branches
        self._exceptions_to_handle = exceptions_to_handle

    def invoke(self, value: object) -> object:
        for index, branch in enumerate(self._branches):
            try:
                return branch.invoke(value)
            except self._exceptions_to_handle:
                if index == len(self._branches) - 1:
                    raise
        raise AssertionError("historical fallback chain is unexpectedly empty")


class _FakeModel:
    def __init__(self, harness: SimpleNamespace, provider_name: str) -> None:
        self._harness = harness
        self._provider_name = provider_name

    def invoke(self, messages: object) -> object:
        del messages
        outcomes = self._harness.outcomes.get(self._provider_name, [])
        if not outcomes:
            raise AssertionError(f"no outcome configured for {self._provider_name}")
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class _StatusError(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.response = SimpleNamespace(status_code=status_code)


class _Clock:
    def __init__(self) -> None:
        self._value = 0.0

    def perf_counter(self) -> float:
        self._value += 0.001
        return self._value


def _module(name: str) -> ModuleType:
    module = ModuleType(name)
    module.__package__ = name.rpartition(".")[0]
    return module


def load_v020_json_client(sha: str) -> tuple[type, object]:
    """Load the pinned v0.2.0 client with SDK/network dependencies replaced."""
    models_source = read_blob(sha, "src/ai_core/models.py")
    client_source = read_blob(sha, "src/ai_core/json_client.py")
    saved = {name: sys.modules.get(name, _MISSING) for name in _MODULE_NAMES}

    httpx = _module("httpx")
    httpx.TimeoutException = type("TimeoutException", (RuntimeError,), {})
    httpx.TransportError = type("TransportError", (RuntimeError,), {})

    messages = _module("langchain_core.messages")
    messages.AIMessage = _Message
    messages.HumanMessage = _Message
    messages.SystemMessage = _Message
    runnables = _module("langchain_core.runnables")
    runnables.RunnableLambda = _RunnableLambda
    langchain_core = _module("langchain_core")
    langchain_core.__path__ = []

    ai_core = _module("ai_core")
    ai_core.__path__ = []
    models = _module("ai_core.models")
    provider_factory = _module("ai_core.provider_factory")

    harness = SimpleNamespace(
        outcomes={},
        build_names=[],
        httpx=httpx,
        message=lambda content, **kwargs: _Message(content, **kwargs),
        status_error=_StatusError,
    )

    def build_chat_model(spec: object) -> _FakeModel:
        harness.build_names.append(spec.name)
        return _FakeModel(harness, spec.name)

    provider_factory.build_chat_model = build_chat_model

    try:
        sys.modules.update(
            {
                "ai_core": ai_core,
                "ai_core.models": models,
                "ai_core.provider_factory": provider_factory,
                "httpx": httpx,
                "langchain_core": langchain_core,
                "langchain_core.messages": messages,
                "langchain_core.runnables": runnables,
            }
        )
        exec(compile(models_source, "<v0.2.0:models.py>", "exec"), models.__dict__)
        client = _module("ai_core.json_client")
        exec(
            compile(client_source, "<v0.2.0:json_client.py>", "exec"),
            client.__dict__,
        )
        client.time = _Clock()
        harness.ProviderConfig = models.ProviderConfig
        return client.LangChainJsonClient, harness
    finally:
        for name, previous in saved.items():
            if previous is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
