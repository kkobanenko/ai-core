# AI Core S2B Phase 3 — Observability Tracing Integration

**Date:** 2026-09-17
**PR:** https://github.com/kkobanenko/ai-core/pull/24
**Branch:** `feat/ai-core-s2b-observability-20260917`
**Base:** `main@c239f0ebb8fa72bdfac96c5083f04d511ebbd7fc`

## What Changed

### `src/ai_core/transports.py`

`execute_transport_attempt()` is now wrapped in a tracing span via `start_llm_span`:

1. **Prompt extraction**: System and user prompts are extracted from `request.messages` for span recording.
2. **Span creation**: `start_llm_span(workflow="transport.{provider_id}", ...)` with attributes:
   - `provider_id`, `model`, `timeout_seconds`, `temperature`
3. **Result recording**: `record_llm_result()` with status (`ok`/`error`), `latency_ms`, optional `error_type` and `response_text`.
4. **Soft-fail guarantee**: All tracing operates via `_SoftSpanContext` which catches exceptions internally. Transport execution is never broken by tracing failures.

### `tests/test_s2b_observability.py` (7 tests)

- Span lifecycle verification (creation, attributes, exit)
- Error outcome recording
- Soft-fail paths (None span, missing Phoenix)
- Health store + tracing coexistence

## S2B Work Package Status

| Phase | Status |
|---|---|
| Phase 1 (Tests) | ✅ Complete (PR #23) |
| Phase 2 (Code) | ✅ Complete (PR #23) |
| Phase 3 (Observability) | ✅ Complete (PR #24) |

**S2B `provider_transports` work package is now fully complete.**

## Test Results

322/322 passed (12.84s)
