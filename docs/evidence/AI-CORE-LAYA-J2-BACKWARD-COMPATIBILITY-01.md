# ai-core Laya J2 shadow — backward compatibility evidence

Date: 2026-10-10

## Baseline (before adapter)

- HEAD: `3d33a743608642c707b15b7877cbbdf90691c258`
- Tests: **431 passed** (`python -m pytest -q`, venv `.venv-bc`)

## Design constraints (additive)

- `invoke_judgment` **unchanged** (J1 mock-only gate preserved).
- `ai_core.__init__.__all__` **unchanged** (no new exported symbols).
- No new required dependencies in `pyproject.toml` (no torch/laya).
- New module: `ai_core.judgment_laya_shadow` — opt-in via `AI_CORE_LAYA_J2_SHADOW_ADAPTER_ENABLED`.
- HTTP transport to `laya-serve`; optional `AI_CORE_LAYA_SHADOW_BEARER_TOKEN`.

## After adapter

- Tests: **438 passed** (+7 new), 0 new failures vs baseline.
- Introduced regressions: **0**

## Compatibility matrix

| Gate | Result |
|------|--------|
| public_api | PASS (`__all__` unchanged) |
| J1_contract | PASS (`invoke_judgment` tests + gate tests) |
| existing_llm_routing | NOT_VERIFIED in this package (no routing code touched) |
| existing_provider_behavior | PASS (mock_judgment path unchanged) |
| configuration_compatibility | PASS (no new required env vars) |
| optional_dependencies | PASS (import ai_core without laya/torch) |
| downstream_consumers | NOT_VERIFIED (SLS contract test separate) |
