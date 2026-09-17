# AI Core S2B Provider Transports Handoff

**Date:** 2026-09-17  
**Status:** implementation complete; PR ready for review and merge  

## Package

S2B provider transports — pure single-attempt HTTP execution over standard library `urllib`.

## Governance and Git

- Authorized by: `platform-control#303` (`docs/decisions/2026-09-17-authorize-ai-core-s2b-provider-transports.md`)
- AI Core branch: `feat/ai-core-s2b-provider-transports-20260917`
- AI Core base SHA: `7fa515c7e148e65e638210332d9f485db586c0e8`

## Delivered Contracts & Implementations

1. **`ProviderTransport` Protocol & Transports (`src/ai_core/transports.py`)**:
   - `OllamaTransport`: handles `/api/chat` calls for `vm100_local_ollama`, `gpu_ollama`, and `ollama_cloud`.
   - `MistralTransport`: handles `/v1/chat/completions` for `mistral_external` with bearer token auth.
   - `get_transport_for_candidate(candidate)`: factory resolving transport by canonical provider ID.
   - `execute_transport_attempt(request, health_store=...)`: single attempt execution with observation recording.

2. **Strict Architectural Guarantees**:
   - **Single Fallback Owner**: Transport executes strictly *one* HTTP call. Zero internal retries or candidate switching. Caller owns workflow loop.
   - **Zero Heavy Dependencies**: Pure standard library `urllib` in core.
   - **Error Classification**: Maps HTTP statuses (429, 401, 403, 400, 404, 5xx), timeouts, socket errors to `ai_core.errors.ErrorDescriptor`.
   - **Observability**: Records latency and updates `ProviderHealthStore` status (`REACHABLE`, `TIMEOUT`, `QUOTA_LIMITED`, `AUTH_FAILED`, `MODEL_MISSING`, `UNREACHABLE`).

3. **Public API Contract**:
   - Root `ai_core.__all__` strictly preserved (the 9 v0.1 symbols unchanged).

## Changed Files

- `src/ai_core/transports.py` (new)
- `src/ai_core/errors.py` (support `.code` on urllib exceptions in `_status_code`)
- `tests/test_s2b_transports.py` (new)
- `docs/handoffs/2026-09-17-ai-core-s2b-provider-transports.md` (new)

## Validation

1. Full test suite: `315 passed in 12.21s` (0 failures, 0 errors).
2. Root API check: `test_v01_public_api_contract.py` 100% green.
3. Code formatting & whitespace: `git diff --check` passed cleanly.
