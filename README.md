# ai-core

Shared Python package for Phoenix tracing, provider bootstrap, JSON completion fallback, and safe span attribute policy. Package contains no LangGraph code, no project-specific domain logic, and targets Python 3.10+.

Projects like `prozakupki-platform`, `Clin-rec`, `zoom-in-plan` consume it as pinned git dependency.

## Install

```bash
pip install "ai-core @ git+ssh://git@github.com/kkobanenko/ai-core.git@v0.2.0"
```

Local development:

```bash
pip install -e ".[dev]"
pytest -q
python -m build
```

## Public API

```python
from ai_core import (
    LangChainJsonClient,
    PhoenixConfig,
    ProviderConfig,
    build_chat_model,
    init_tracing,
    load_phoenix_config,
    shutdown_tracing,
    start_llm_span,
)
```

### ProviderConfig contract

`ProviderConfig` fields:

- `name`: logical provider name, e.g. `openai`, `mistral`, `ollama`
- `transport`: transport selector: `openai_compatible` or `ollama_native`
- `model`: upstream model id
- `base_url`: provider endpoint; may be empty only for native OpenAI endpoint
- `api_key`: provider secret; may be empty only when `api_key_optional=True`
- `api_key_optional`: allow provider without key
- `timeout_seconds`: per-request timeout
- `headers`: optional HTTP headers for transport-specific auth/proxy cases

`ProviderConfig.is_ready()` requires model plus endpoint, except native OpenAI endpoint may omit `base_url`.

### Supported providers and transports

- `transport="openai_compatible"`: OpenAI-compatible chat providers via `langchain-openai`
- `name="mistral"`: Mistral provider via `langchain-mistralai`
- `transport="ollama_native"`: Ollama via `langchain-ollama`

`build_chat_model()` rejects unsupported pairs with `ValueError`.

### Transport-only fallback

`LangChainJsonClient` accepts ordered `ProviderConfig` tuple, filters not-ready entries, then executes providers in order. Fallback triggers only for transport-level failures:

- timeout
- `httpx.TransportError`
- HTTP `429`
- HTTP `5xx`

Non-transport exceptions stay terminal and stop chain. `attempt_summary` records provider, model, attempt index, outcome, reason, latency.

### Tracing defaults

Phoenix tracing is env-driven and soft-fail:

- `PHOENIX_ENABLED=false` by default
- `PHOENIX_TRACE_INCLUDE_IO=false` by default
- metadata-only tracing is default behavior
- prompt/response bodies attach only when IO flag enabled
- all IO fields truncated by `PHOENIX_TRACE_MAX_IO_CHARS`
- only allowlisted scalar metadata survives `sanitize_span_attributes()`

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `PHOENIX_ENABLED` | `false` | Master tracing switch |
| `PHOENIX_COLLECTOR_ENDPOINT` | `http://127.0.0.1:6006/v1/traces` | Phoenix OTLP HTTP endpoint |
| `PHOENIX_PROJECT_NAME` | *(empty)* | Phoenix project name |
| `PHOENIX_TRACE_INCLUDE_IO` | `false` | Attach truncated prompt/response bodies |
| `PHOENIX_TRACE_MAX_IO_CHARS` | `4000` | Char cap per IO field |

## Example

```python
from ai_core import LangChainJsonClient, ProviderConfig, init_tracing, shutdown_tracing, start_llm_span

init_tracing(project_name="prozakupki-platform")

client = LangChainJsonClient(
    (
        ProviderConfig(
            name="openai",
            transport="openai_compatible",
            model="gpt-4.1-mini",
            base_url="",
            api_key="...",
            api_key_optional=False,
            timeout_seconds=30,
        ),
        ProviderConfig(
            name="ollama",
            transport="ollama_native",
            model="qwen2.5:14b",
            base_url="http://127.0.0.1:11434",
            api_key="",
            api_key_optional=True,
            timeout_seconds=60,
            headers={"Authorization": "Bearer proxy-token"},
        ),
    )
)

with start_llm_span(
    workflow="classify",
    attributes={"llm.provider": "openai", "llm.model": "gpt-4.1-mini"},
    system_prompt="...",
    user_prompt="...",
) as span:
    result = client.create_json_completion("...", "...")
    if span is not None:
        span.set_attribute("llm.status", "success")
        span.set_attribute("llm.output_tokens", result.output_tokens)

shutdown_tracing()
```

## Smoke test

```bash
PHOENIX_ENABLED=true PHOENIX_PROJECT_NAME=smoke python examples/smoke_span.py
```

Span should appear in Phoenix UI through local tunnel at `127.0.0.1:6006`.
