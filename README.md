# ai-core

Тонкая shared-библиотека для Phoenix observability: конфигурация из env, soft-fail tracing, обрезка IO в трейсах.

Проекты `prozakupki-platform`, `zoom-in-plan` и будущий `clin-rec` подключают пакет как git-зависимость.

Пакет не содержит credentials или business code.

## Установка (prozakupki-platform / zoom-in-plan / clin-rec)

```text
pip install "ai-core @ git+https://github.com/kkobanenko/ai-core.git@v0.1.0"

Production default:
PHOENIX_ENABLED=false
PHOENIX_TRACE_INCLUDE_IO=false
PHOENIX_TRACE_MAX_IO_CHARS=4000
```

Локальная разработка:

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `PHOENIX_ENABLED` | `false` | Главный переключатель tracing |
| `PHOENIX_COLLECTOR_ENDPOINT` | `http://127.0.0.1:6006/v1/traces` | OTLP HTTP endpoint Phoenix |
| `PHOENIX_PROJECT_NAME` | *(пусто)* | Имя проекта в Phoenix UI (`prozakupki-platform`, `clin-rec`, `zoom-in-plan`) |
| `PHOENIX_TRACE_INCLUDE_IO` | `false` | Прикреплять обрезанные prompt/response к span |
| `PHOENIX_TRACE_MAX_IO_CHARS` | `4000` | Лимит символов на одно IO-поле |

Пример для **Clin-rec**:

```bash
PHOENIX_ENABLED=true
PHOENIX_PROJECT_NAME=clin-rec
PHOENIX_COLLECTOR_ENDPOINT=http://127.0.0.1:6006/v1/traces
```

Пример для **zoom-in-plan**:

```bash
PHOENIX_ENABLED=true
PHOENIX_PROJECT_NAME=zoom-in-plan
PHOENIX_COLLECTOR_ENDPOINT=http://127.0.0.1:6006/v1/traces
```

## Публичный API (Phase 1)

```python
from ai_core import init_tracing, maybe_truncate, shutdown_tracing, start_llm_span
from ai_core import PhoenixConfig, load_phoenix_config

init_tracing(project_name="prozakupki-platform")

with start_llm_span(
    workflow="classify",
    attributes={"model": "gpt-4o-mini"},
    system_prompt="...",
    user_prompt="...",
) as span:
    # ... вызов LLM ...
    if span is not None:
        span.set_attribute("llm.output", maybe_truncate(response, 4000))

shutdown_tracing()
```

## Smoke-тест (Phoenix UI)

```bash
PHOENIX_ENABLED=true PHOENIX_PROJECT_NAME=smoke python examples/smoke_span.py
```

Span должен появиться в Phoenix UI (через SSH tunnel на `127.0.0.1:6006`).

---

## Высокоуровневый Runtime & Executor (v0.3+)

Начиная с `v0.3.0` (и hardening в `v0.3.1`), `ai-core` предоставляет детерминированный single-loop runtime и высокоуровневый фасад `execute_chat`:

```python
from ai_core.executor import execute_chat, execute_prompt
from ai_core.routing import RouteCandidate

# 1. Быстрый вызов промпта с дефолтным каскадом (vm100_local_ollama -> gpu_ollama -> mistral_external):
result = execute_prompt("Привет! Расскажи о статусе системы.")
print(result.content)
print(f"Winner: {result.winner.provider_id}, Fallback occurred: {result.fallback_occurred}")

# 2. Вызов чата с явным контролем кандидатов и дедлайна:
result = execute_chat(
    messages=[{"role": "user", "content": "Классифицируй входящий документ"}],
    candidates=[
        RouteCandidate(provider_id="vm100_local_ollama", model="qwen3:8b"),
        RouteCandidate(provider_id="gpu_ollama", model="qwen3:8b"),
    ],
    total_timeout_seconds=15.0,
)
```
