from __future__ import annotations

import time
from dataclasses import asdict, replace

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda

from ai_core.models import AttemptRecord, JsonCompletion, ProviderConfig
from ai_core.provider_factory import build_chat_model


class ProviderTransportError(RuntimeError):
    pass


def _status_code(error: BaseException) -> int | None:
    value = getattr(error, "status_code", None)
    if isinstance(value, int):
        return value
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _is_fallback_eligible(error: BaseException) -> bool:
    status = _status_code(error)
    return isinstance(error, (TimeoutError, httpx.TimeoutException, httpx.TransportError)) or status == 429 or bool(status and 500 <= status <= 599)


class LangChainJsonClient:
    def __init__(self, providers: tuple[ProviderConfig, ...]):
        self._providers = tuple(item for item in providers if item.is_ready())

    def is_ready(self) -> bool:
        return bool(self._providers)

    def create_json_completion(self, system_prompt: str, user_prompt: str) -> JsonCompletion:
        if not self._providers:
            raise RuntimeError("AI client is disabled")
        attempts: list[AttemptRecord] = []
        messages = [SystemMessage(system_prompt), HumanMessage(user_prompt)]

        def branch(spec: ProviderConfig, index: int):
            model = build_chat_model(spec)

            def invoke(_: object) -> JsonCompletion:
                started = time.perf_counter()
                try:
                    message = model.invoke(messages)
                except BaseException as error:
                    elapsed = int((time.perf_counter() - started) * 1000)
                    if _is_fallback_eligible(error):
                        attempts.append(
                            AttemptRecord(
                                spec.name,
                                spec.model,
                                index,
                                "transport_error",
                                error.__class__.__name__,
                                elapsed,
                            )
                        )
                        raise ProviderTransportError(str(error)) from error
                    attempts.append(
                        AttemptRecord(
                            spec.name,
                            spec.model,
                            index,
                            "terminal_error",
                            error.__class__.__name__,
                            elapsed,
                        )
                    )
                    raise
                elapsed = int((time.perf_counter() - started) * 1000)
                usage = getattr(message, "usage_metadata", None) or {}
                attempts.append(AttemptRecord(spec.name, spec.model, index, "success", "ok", elapsed))
                return JsonCompletion(
                    raw_content=str(message.content or ""),
                    provider_name=spec.name,
                    model_name=str((getattr(message, "response_metadata", None) or {}).get("model_name") or spec.model),
                    input_tokens=int(usage.get("input_tokens") or 0),
                    output_tokens=int(usage.get("output_tokens") or 0),
                    latency_ms=elapsed,
                )

            return RunnableLambda(invoke)

        branches = [branch(spec, index) for index, spec in enumerate(self._providers, start=1)]
        runnable = branches[0].with_fallbacks(branches[1:], exceptions_to_handle=(ProviderTransportError,))
        result = runnable.invoke({})
        return replace(result, attempt_summary=tuple(asdict(item) for item in attempts))
