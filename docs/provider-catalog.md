# Provider catalog (ai-core v0.2.1)

Канонические `provider_id` (четыре **раздельные** идентичности):

| provider_id | boundary | raw PII | sanitized PII |
|-------------|----------|---------|---------------|
| `vm100_local_ollama` | `LOCAL_SAME_HOST` | allow | allow |
| `ollama_cloud` | `EXTERNAL_CLOUD` | deny | allow |
| `gpu_ollama` | `UNKNOWN_BOUNDARY` | deny | allow |
| `mistral_external` | `EXTERNAL_CLOUD` | deny | allow |

## API

```python
from ai_core import get_provider_catalog, get_provider_profile

catalog = get_provider_catalog()
profile = get_provider_profile("vm100_local_ollama")
```

`ProviderProfile` содержит политики, capabilities, `priority_hint` и **имена**
env-ключей (`endpoint_env_keys`, `credential_env_keys`, `default_model_env`).
Значения секретов и API keys в каталог **не** входят.

## Historical names

Поле `historical_names` — только для сопоставления со старыми конфигами
(например `ollama_local`, `local_gpu_ollama`, `mistral`). Канонический id —
новый контракт.

## Chains

Универсальной цепочки fallback **нет**. Примеры исторических цепочек
продуктов разные (Prozakupki vs Zoom) — см. evidence A610.

## Health

Проверка здоровья — **per `provider_id`**. Quota у `ollama_cloud` не должна
помечать `vm100_local_ollama` / `gpu_ollama` как down.
