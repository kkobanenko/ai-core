# Surrogate data (ai-core v0.2.1)

Локальная замена PII **до** отправки во внешний контур.

## Режимы

- `TOKENIZED` — `[EMAIL_1]`, `[PHONE_1]`, …
- `FORMAT_PRESERVING_SYNTHETIC` — синтетический email/phone с сохранением формы;
  email всегда на домене `.invalid` (RFC 2606)

## Entity kinds

`PHONE`, `EMAIL`, `PERSON_NAME`, `ADDRESS`, `ACCOUNT_IDENTIFIER`,
`URL_USERINFO`, `URL_SECRET_QUERY`, `FORM_FREE_TEXT`, `OTHER_CONFIGURED_PII`,
`SECRET`.

## SECRET

SECRET-подобные значения **никогда** не суррогатируются. Действия:

- `DROP` — вырезать из payload
- `BLOCK` — остановить обработку (`SurrogateResult.blocked=True`)

## SurrogateResult

- `safe_payload` — можно отправлять провайдеру (после DLP)
- `surrogate_manifest` — обезличенный список замен (без оригиналов)
- `local_surrogate_map` — **только локально**: surrogate → original

### Запрет на утечку map

`local_surrogate_map` **нельзя**:

- отправлять провайдеру
- писать в логи / Phoenix traces / span attributes
- класть в shared storage без отдельного encrypted vault

После запроса вызывайте `clear_local_map()`.

## DLP

Перед EXTERNAL_CLOUD:

```python
from ai_core import apply_surrogate, outbound_leak_check, clear_local_map

result = apply_surrogate(raw_text)
check = outbound_leak_check(result.safe_payload, original_sensitive_values=[...])
# если check.decision == BLOCK_EXTERNAL_EGRESS — не отправлять
clear_local_map()
```
