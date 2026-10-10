# AI-CORE Laya J2 — backward compatibility (LAYA-04)

Date: 2026-10-10  
Branch: `feat/judgment-laya-j2-shadow`

## Regression

| Suite | Result |
|-------|--------|
| Full `pytest` | **441 passed** |
| `test_backward_compatibility_laya_gate` | PASS |
| `test_c3_v2_bounded_routing` | PASS |
| `test_sls_consumer_contract` | PASS |
| `invoke_judgment` mock-only | unchanged |
| `ai_core.__all__` | unchanged |

## Additive changes

- `judgment_laya_endpoint.py` — LOCAL_SAME_HOST admission, no redirects, proxy strip, response size bound
- `judgment_laya_shadow.py` — probability validation, duplicate answer rejection

## existing_llm_routing

**PASS** (routing modules untouched; bounded routing + consumer contract tests green on PR branch).
