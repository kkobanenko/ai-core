# A620–A640 — Implementation evidence (provider catalog / privacy / routing)

Дата: 2026-08-07  
Пакет: `ai-core` **0.2.1 candidate** (git tag **не** создавался; `v0.2.0` не изменялся).  
Ветка: `feat/provider-catalog-privacy-routing`  
Base: immutable `v0.2.0` SHA `e479d0af314714a96c959a2ea677abdcb0942af7`

## Scope delivered

| ID | Содержание | Статус |
|----|------------|--------|
| A620 | `provider_catalog.py` — 4 canonical ids, profiles, env key names only | done |
| A630 | `privacy.py` + `surrogate.py` + `dlp.py` | done |
| A640 | `routing.py` + `health.py` (per-provider isolation) + exports + docs + tests | done |

## Modules

- `src/ai_core/provider_catalog.py`
- `src/ai_core/privacy.py`
- `src/ai_core/surrogate.py`
- `src/ai_core/dlp.py`
- `src/ai_core/routing.py`
- `src/ai_core/health.py`
- Docs: `docs/provider-catalog.md`, `docs/privacy-routing.md`, `docs/surrogate-data.md`
- Evidence: `docs/evidence/A610-provider-inventory.md`, this file

## Compatibility

- Все публичные символы v0.2.0 сохранены (`ProviderConfig`, `build_chat_model`, `LangChainJsonClient`, tracing, …).
- Новые символы добавлены аддитивно в `__init__.__all__`.
- `pyproject.toml` version → `0.2.1` (candidate only).

## Safety properties claimed

1. Sensitive RAW не выбирает `EXTERNAL_CLOUD`.
2. Исчерпание RAW → `RawRouteExhaustedError`, без auto-forward raw в cloud.
3. `quota_limited` на `ollama_cloud` не помечает `vm100_local_ollama` / `gpu_ollama`.
4. `local_surrogate_map` документирован как never-to-provider/logs/traces.
5. Ollama health probe бьёт только `/api/tags` (без page content); Authorization не логируется кодом probe.

## Tests

Запуск: `python -m pytest -q`

Ожидаемые новые файлы:

- `tests/test_provider_catalog.py`
- `tests/test_provider_health_isolation.py`
- `tests/test_surrogate.py`
- `tests/test_dlp.py`
- `tests/test_routing_privacy.py`
- `tests/test_v02_compat_exports.py`

## Limitations

- Live probes с agent workstation: vm100/gpu unreachable; cloud/mistral — unknown без credentials.
- Детекция PII — regex-based, не NLP; ложные срабатывания/пропуски возможны.
- `gpu_ollama` boundary остаётся UNKNOWN до ADR.
- Роутер не подменяет `LangChainJsonClient`; потребитель сам передаёт eligible configs.
