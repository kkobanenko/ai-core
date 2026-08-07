# Privacy-aware routing (ai-core v0.2.1)

## DataClass

- `SYNTHETIC` — синтетика, можно на любой authorized healthy provider
- `PUBLIC_NO_PII` — публичное без PII
- `PUBLIC_POSSIBLE_PII` / `PRIVATE_CLIENT_DATA` — чувствительные
- `SECRET` — секреты; RAW не отправляется через этот слой

## OutboundForm

- `RAW` — исходный текст
- `SANITIZED` — вычищенный / redacted
- `SURROGATED` — заменён суррогатами (см. surrogate-data.md)

## Правила

1. **RAW + sensitive** — только провайдеры с `raw_pii_policy=allow`
   (в каталоге v0.2.1 это `vm100_local_ollama`). EXTERNAL_CLOUD не eligible.
2. **SANITIZED / SURROGATED** — `sanitized_pii_policy=allow`; EXTERNAL_CLOUD
   может быть eligible после DLP.
3. **SYNTHETIC** — все authorized healthy провайдеры с `supports_text`.
4. Health хранится **отдельно** на каждый `provider_id`.
5. Если RAW-маршрут исчерпан → `RawRouteExhaustedError` с рекомендацией
   сделать **новый** sanitized/surrogated запрос. Авто-отправки raw во
   внешнее облако **нет**.

## API

```python
from ai_core import (
    DataClass,
    OutboundForm,
    PrivacyAwareRouter,
    ProviderHealthStore,
    RawRouteExhaustedError,
)

store = ProviderHealthStore()
router = PrivacyAwareRouter(health_store=store)

# Sensitive RAW — только local-eligible
ids = router.select_or_raise_raw(DataClass.PRIVATE_CLIENT_DATA, OutboundForm.RAW)

# После sanitize — облако может войти в набор
ids = router.select_eligible_providers(
    DataClass.PRIVATE_CLIENT_DATA,
    OutboundForm.SANITIZED,
)
```

Fallback между провайдерами внутри eligible-набора остаётся у
`LangChainJsonClient` (как в v0.2.0).
