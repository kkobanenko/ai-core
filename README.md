# ai-core

Тонкая shared-библиотека для Phoenix observability: конфигурация из env, обрезка IO в трейсах.

Проекты `prozakupki-platform`, `Clin-rec`, `zoom-in-plan` могут подключить пакет как git-зависимость на следующих этапах rollout.

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `PHOENIX_ENABLED` | `false` | Главный переключатель tracing |
| `PHOENIX_COLLECTOR_ENDPOINT` | `http://127.0.0.1:6006/v1/traces` | OTLP HTTP endpoint Phoenix |
| `PHOENIX_PROJECT_NAME` | *(пусто)* | Имя проекта в Phoenix UI (`prozakupki-platform`, `clin-rec`, `zoom-in-plan`) |
| `PHOENIX_TRACE_INCLUDE_IO` | `true` | Прикреплять обрезанные prompt/response к span |
| `PHOENIX_TRACE_MAX_IO_CHARS` | `4000` | Лимит символов на одно IO-поле |

## Установка (разработка)

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## Публичный API (Phase 1)

```python
from ai_core import PhoenixConfig, load_phoenix_config, maybe_truncate

cfg = load_phoenix_config()
if cfg.enabled:
    truncated = maybe_truncate(long_prompt, cfg.max_io_chars)
```

Tracing (`init_tracing` / `shutdown_tracing`) — в следующей задаче.
