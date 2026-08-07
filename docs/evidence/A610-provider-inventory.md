# A610 — Provider inventory (evidence)

Дата фиксации: 2026-08-07. Источник: известный inventory продуктов (Prozakupki / Zoom / platform), **без** live credentials в agent env.

**Не изобретаем одну универсальную fallback-цепочку.** Исторические цепочки продуктов различаются.

| id | historical | backend | boundary hypothesis | env keys (names only) | consumers | live probe from this host |
|----|------------|---------|---------------------|----------------------|-----------|---------------------------|
| `vm100_local_ollama` | ollama sidecar 127.0.0.1 on VM100; zoom `ollama_local` | ollama | `LOCAL_SAME_HOST` | `OLLAMA_*` / 127.0.0.1:11434 | prozakupki historical, zoom `ollama_local` | workstation probe: unreachable (curl 7) |
| `ollama_cloud` | `ollama_cloud` | ollama | `EXTERNAL_CLOUD` | `OLLAMA_API_KEY`, `AI_PROVIDER` | prozakupki classifier primary often | unknown (no credentials in agent env) |
| `gpu_ollama` | `local_gpu_ollama`, `gpu-ollama`, `100.91.166.5:11434` Tailscale | ollama | `UNKNOWN_BOUNDARY` (private net but separate host; ADR-016 candidate only) | `LOCAL_GPU_OLLAMA_*` | zoom, prozakupki, clin_rec/platform | timeout/unreachable from this host |
| `mistral_external` | `mistral` | mistral | `EXTERNAL_CLOUD` | `MISTRAL_API_KEY` | prozakupki fallback | unknown (no credentials) |

## Historical chain examples (not universal)

- Prozakupki (пример): `ollama_cloud` → `mistral` → `local_gpu_ollama`
- Zoom (пример): `local_gpu_ollama` → `ollama_local`

В каталоге ai-core v0.2.1 канонические id: `ollama_cloud`, `mistral_external`, `gpu_ollama`, `vm100_local_ollama`.

## Notes

- Секреты и значения ключей в evidence **не** записывались.
- `gpu_ollama` оставлен как `UNKNOWN_BOUNDARY`: Tailscale path существует, но raw PII auto-allow запрещён до отдельного ADR.
- Probe с рабочей станции агента не является probe с VM100; статус «unreachable» здесь — про этот host, не про production VM100 sidecar.
