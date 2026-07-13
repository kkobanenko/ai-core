"""Smoke-тест: отправить hello-span в Phoenix UI."""

import os

os.environ.setdefault("PHOENIX_ENABLED", "true")
os.environ.setdefault("PHOENIX_PROJECT_NAME", "smoke")

from ai_core.tracing import init_tracing, start_llm_span

init_tracing()
with start_llm_span(
    workflow="smoke",
    attributes={"model": "none"},
    user_prompt="hello",
) as span:
    if span is not None:
        span.set_attribute("llm.output", "ok")

print("smoke span sent (if Phoenix up)")
