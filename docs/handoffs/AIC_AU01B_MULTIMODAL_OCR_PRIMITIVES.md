# AIC-AU01B — Multimodal / OCR single-provider primitives

**STATUS:** implementation spike (draft PR only)  
**BASE:** immutable `v0.2.1` (`f743057a02a8b69bf943b615510d4745d737e16a`)  
**BRANCH:** `spike/au01b-multimodal-ocr-primitives`  
**NO RELEASE / NO TAG / NO MAIN MERGE / NO CONSUMER CHANGES**

## Purpose

Add **generic, single-provider** vision and PDF-OCR transport primitives to `ai-core`, plus a **model-specific** capability contract. Consumers (Alpha, Prozakupki) own chains, prompts, rights, and quality policy.

## Generic boundary

| Owns | Does **not** own |
|------|------------------|
| Provider identity + endpoint/credential env resolution | Provider fallback chains |
| Model capability metadata (`ProviderCapability`) | Alpha copyright / SOURCE_VERIFIED / rights enums |
| One-shot HTTP transport (Ollama vision, Mistral OCR) | Product IDs, MinIO, GPU slots, job semantics |
| Privacy eligibility composition (`DataClass` / `OutboundForm`) | Workflow prompts / quality continuation |
| Transport error normalization + safe Phoenix attrs | Nested retry that multiplies billable calls |

## Single-provider rule

- `invoke_vision(...)` → **at most one** upstream Ollama `/api/generate` POST.
- `invoke_pdf_ocr(...)` → **at most one** upstream Mistral `/ocr` POST.
- No `invoke_with_fallback`, `ocr_provider_chain`, `try_providers_until_success`, or `chain_runner`.
- Router returns eligibility; it does **not** execute provider fallback.

## Capability model

Public enum: `ProviderCapability` = `TEXT | STRUCTURED_JSON | VISION_IMAGE | OCR_PDF`.

Immutable `ProviderModelProfile(provider_id, model, capabilities)` with lookup APIs:

- `get_model_profile` / `model_has_capability` / `require_model_capability` / `list_model_profiles`

Proven profiles only:

| provider | model | capabilities |
|----------|-------|--------------|
| `gpu_ollama` | `qwen2.5vl:7b` | `VISION_IMAGE`, `TEXT` |
| `mistral_external` | `mistral-ocr-latest` | `OCR_PDF` |
| `gpu_ollama` | `qwen3.5:9b` | `TEXT`, `STRUCTURED_JSON` (not vision) |
| `mistral_external` | `ministral-8b-2512` | `TEXT`, `STRUCTURED_JSON` (not OCR) |

Unknown models are **not** assumed multimodal.  
`ProviderProfile.supports_multimodal` remains `False` (API preserved; capability is model-specific).

## Credential ownership

Catalog stores **env names only** (`MISTRAL_API_KEY`, `LOCAL_GPU_OLLAMA_API_KEY`, …).  
`resolve_provider_endpoint` reads values from `os.environ`.  
Secrets must not appear in `repr()`, exceptions, logs, trace attributes, or `MediaResult.metadata`.

## Public types / functions (additive)

- Types: `VisionImageRequest`, `OcrPdfRequest`, `MediaResult`, `MediaTransportError`, `MediaAuthError`, `MediaPrivacyError`, `ResolvedProviderEndpoint`
- Functions: `invoke_vision`, `invoke_pdf_ocr`, `build_ollama_vision_payload`, `build_mistral_ocr_payload`, `assert_media_allowed`, `resolve_provider_endpoint`, capability helpers above

## Privacy vs rights

- Privacy: existing `PrivacyAwareRouter` / `is_eligible_for_outbound` — RAW sensitive external egress stays blocked.
- Rights (CC_BY, UNKNOWN_RIGHTS, SOURCE_VERIFIED, HUMAN_REVIEWED): **Alpha-owned**; not added here.

## Tracing

Phoenix surface reused via shared `sanitize_span_attributes` / `set_safe_span_attributes`.  
Namespaced safe keys only: `llm.provider`, `llm.model`, `llm.status`, `llm.latency_ms`, `llm.input_tokens`, `llm.output_tokens`, `ai.capability`, `media.page_count`, `media.image_count`, `media.page_count_requested`.  
Default `PHOENIX_TRACE_INCLUDE_IO=false` — no raw image/PDF bytes or full OCR text in spans. No direct `span.set_attribute` bypass from media code.

## Senior-review repairs (AIC-AU01B1)

Architecture accepted; mandatory fixes applied before any release review:

1. **MediaResult repr is content-free** — metadata only (`chars`, counts); no text/preview/OCR excerpt.
2. **Privacy classification is mandatory** — `data_class` and `outbound_form` are required keyword-only args on `invoke_vision` / `invoke_pdf_ocr` (no `PUBLIC_NO_PII` / `SANITIZED` defaults).
3. **Base64 ≠ sanitization** — encoding for wire transport does not change outbound form. Unchanged image/PDF bytes must be declared `OutboundForm.RAW` by the caller. `SANITIZED` only after the consumer actually produced a sanitized representation.
4. **Trace attributes use shared allowlist** — namespaced keys only; `set_safe_span_attributes` wraps `sanitize_span_attributes`.
5. **Credential optionality is explicit** — `ProviderProfile.api_key_optional` on catalog entries; resolver has no `endswith("ollama")` heuristics. `AI_PROVIDER` is not a credential env key.
6. **Vision input is bytes-only** — paths/URLs/base64 strings rejected with `TypeError` before any network call.

Alpha copyright/rights remain outside ai-core: Alpha decides whether source bytes may leave the product boundary, then passes explicit `data_class` / `outbound_form`.

## Consumer integration (future — not in this WP)

- **Alpha:** call `invoke_vision` / `invoke_pdf_ocr` in a consumer-owned loop; keep quality policy and copyright egress outside ai-core.
- **Prozakupki:** may later replace local transport helpers with these primitives; do **not** move `chain_runner` into ai-core.
- **No consumer pin/migration in this spike.**

## Verification

- CI: mocked HTTP only (`LIVE_PROVIDER_CALLS=0`).
- Existing v0.2.1 tests must pass; changes are additive.
- Secret scan of diff: no `.env`, no API key values.

## Explicit non-goals

- No release, tag, or merge to `main`.
- No nested fallback API.
- No live provider smoke in this WP.
