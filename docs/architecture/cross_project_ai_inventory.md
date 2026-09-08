# Cross-project AI inventory

**Evidence window:** 2026-09-08–2026-09-09

**Method:** read-only inventory of every top-level entry under
`/home/kok4444/projects`, followed by source-context inspection of positive
matches. Generated caches, vendored/upstream repositories, worktrees, evidence
artifacts, and build copies were not treated as independent consumers.

## Interpretation rules

- `HEAD` means the recorded tracked checkout, not necessarily production.
- `origin/main` is stated explicitly where the remote default branch was used.
- An AI-core HTTP **client** does not prove that a compatible AI-core server is
  deployed or even implemented.
- A config entry proves configuration intent, not runtime model capability.
- Privacy is marked unknown when no enforceable egress rule was found; absence
  of evidence is not interpreted as permission.

## Allowlist reconciliation

`platform-control/config/projects.yaml@origin/main` contains six coordinated
projects. Every one is classified below.

| Allowlisted project | Observed revision | AI classification | Current boundary |
|---|---|---|---|
| `platform_control` | `origin/main@6445a2ed8614ae0bb663b92413ebf04f3fbc1d99` | no provider runtime; governance/control plane | Accepted ADRs, compatibility matrix, initiatives and locks |
| `ai_core` | `main@7569441c18362cfd15524ad73f56f7f35580c86f` | yes, shared tracing package | tracing/config/IO only on default branch |
| `prozakupki` | checkout `70f9cf001b3073132858236bbf653b687a139cc7`; `origin/main@2fd7fd705417660ce62c4e11981727f51e625b99` | yes, broad production-style AI estate | local implementation authoritative; `v0.2.0` adapter optional |
| `zoom` | checkout `90f0665f665bd8434b60df7563107c7488c33c44`; remote default observed `9cc80497baa748937ee7e7e2eb48f80fa398446b` | yes | `v0.1.0` tracing plus consumer-owned execution |
| `clin_rec` | checkout `950a21c60dd353f69bc3a7e067bc5a4820df6462`; `origin/main@1d16d54bfcd0631388cf29450a1c82ed233968f2` | yes | no ai-core; consumer-owned LangChain factory/fallback |
| `alpha_university` | `main/origin/main@7216b379518cd4d5e934daeb50bdd5a6cb503d8a` | AI-adjacent; deterministic OCR shadow, no LLM runtime dependency found | accepted narrow AI-core boundary; Planner remains AI-independent |

The embedded `observed_*` fields in platform-control are historical inventory
snapshots and differ from several current checkouts; they are not silently
substituted for the revisions above.

## Normalized consumer inventory

| Project | Current AI path | ai-core pin | Providers / models | Registry / direct client | Retry / fallback | Privacy / tracing | Vision, OCR, STT | Migration risk |
|---|---|---|---|---|---|---|---|---|
| **ai-core main** | Phoenix tracing/config/IO policy | package version 0.1.0 line | none | no provider client | none | safe-attribute allowlist; IO off by default | none | High if provider line replaces rather than additively extends root/dependencies |
| **Prozakupki** | legacy and optional LangChain JSON paths; separate media routes/workers | Docker pins `v0.2.0`; production default `AI_ADAPTER=legacy` | OpenAI `gpt-4o-mini-2024-07-18`, `whisper-1`; Mistral `ministral-8b-2512`, `voxtral-mini-latest`; `mistral-ocr-latest`; DeepSeek `deepseek-chat`; Ollama/local GPU/cloud models including `qwen3.5:9b`, `qwen3.6:35b`, `qwen3-vl:4b`, `gemma4`; faster-whisper | `config/ai_providers.yaml`; direct OpenAI/httpx/native Ollama `/api/chat`; `LangChainJsonClient` adapter | local retry helper; timeout/429 same-provider retry; transport/5xx fallback; multiple media-specific loops | per-feature controls; no single central policy evidenced; tracing/Phoenix integration | text/JSON, image description, OCR, STT | **Very high**: richest evidence source, multiple owners and rollback paths; migrate late |
| **KMO** | operations-service chat stack copied from Prozakupki; separate image-description client | none | local GPU Ollama `qwen3.6:35b`; Ollama cloud `gemma4`; Mistral `open-mistral-nemo`; config also contains OpenAI/DeepSeek/local Ollama | copied `ai_providers.yaml`; direct httpx/OpenAI/native `/api/chat` | retry inside provider plus ordered fallback chain | authenticated product API; no enforceable outbound privacy classifier found in chat layer | image-description integration; no canonical media ownership | **Very high**: duplicated registry/client/retry/fallback; read-only until representability proven |
| **Zoom** | consumer runtime with raw Ollama and LangChain Ollama adapters | `v0.1.0` | `local_gpu_ollama/qwen3.6:35b`; `ollama_local/qwen3.5:9b` | local YAML; raw `/api/chat`; single-provider LangChain adapter | consumer owns one failover loop; timeout is currently per attempt; `AI_RUNTIME_ADAPTER=raw` rollback | ai-core tracing; central egress classification not evidenced | text/JSON | High: depends on exact v0.1 root API and consumer fallback ownership |
| **Clin-rec** | local LangChain provider factory/runtime | not installed | default `ollama_cloud/gemma3:4b` -> Mistral `mistral-small-latest` -> `local_gpu_ollama`; timeout 180s | consumer factory using LangChain Ollama/Mistral | fallback on timeout/429/5xx; other errors terminal | local Phoenix config; no central privacy layer evidenced | text/structured clinical output | High: LangChain `<1` constraints conflict with historical ai-core v0.2 dependency family |
| **Landing Sell** | privacy envelope -> `LandingSellAIGateway` -> ai-core `LangChainJsonClient` | exact HTTPS `v0.2.1` | local `ollama/llama3.2`; optional Mistral; accepted provider privacy identities | product gateway builds ai-core `ProviderConfig`; no direct provider client | ai-core is fallback owner; per-provider retries disabled; deterministic product fallback | explicit RAW/SANITIZED/SYNTHETIC envelope, DLP, fail-closed raw exhaustion; metadata-only policy | multimodal unavailable | High: v0.2.1 root API and privacy semantics; generic `ollama` must not be guessed by future aliasing |
| **agent-lab** | sole intended LLM path via `ai_core_adapter` | exact HTTPS `v0.2.1` | `gpu_ollama` -> `vm100_local_ollama`; aliases `agent-worker/qwen2.5vl:7b`, `reviewer/qwen3.6:35b` | ai-core catalog and `LangChainJsonClient`; product alias YAML | ai-core client owns provider chain | internal/metadata-oriented contract; local fallback classes exist when import fails | text/JSON; a vision-capable model is named but task capability must remain explicit | Medium-high: local stand-ins can mask missing package behavior; aliases are product concerns |
| **transcription-service** | chunk/canonicalize locally, call internal AI-core STT HTTP contract when enabled | no library pin; HTTP only | provider/model intentionally opaque to client | `POST /internal/ai/v1/transcriptions`, service key header | worker durable `max_attempts=3`; HTTP 429/5xx/transport retryable | no raw response body in errors/logs; product service auth | segment-timestamp STT | High/blocking: client is in `origin/main`, safe default is `fake`, but current ai-core has no server endpoint and `STT_SEGMENTS` is unaccepted |
| **image-description-service** | normalize/store locally, call internal AI-core image-description HTTP contract when enabled | no library pin; HTTP only | provider/model intentionally opaque to client | `POST /internal/ai/v1/image-descriptions`, service key header | worker durable `max_attempts=3`; HTTP 429/5xx/transport retryable | no raw response body in errors/logs; product service auth | bilingual image description | High/blocking: client is in `origin/main`, safe default is `fake`, but current ai-core has no server endpoint/runtime |
| **Alpha University** | deterministic Planner; selective Tesseract OCR shadow on a frozen 13-page set | none | Tesseract OCR; no LLM provider/model dependency found on main | product OCR modules, no provider HTTP/SDK found | idempotent shadow workflow; no LLM fallback | ADR-023 requires tracing-safe narrow boundary and product-owned domain/schema behavior | OCR candidate layer, noncanonical/non-authoritative | Low now; future AI shadow needs new approval, frozen benchmark, no-cloud/privacy contract, zero false-supported |

## Evidence by material project

### Prozakupki

Observed on the tracked checkout branch
`feat/img2a-image-description-contract-20260906@70f9cf0`; it must not be
presented as the production default branch.

- Registry/models/capabilities: `config/ai_providers.yaml`.
- Shared JSON path: `libs/procurement-core/procurement_core/ai/json_client.py`
  and `ai/retry.py`.
- Legacy/adapter switch: `services/zakupki-monitor/utils/ai_provider.py` and
  `ai_adapters.py`; tests in `services/zakupki-monitor/tests/test_ai_adapters.py`.
- Pin: `services/zakupki-monitor/Dockerfile` (`v0.2.0`).
- Structured JSON: `libs/procurement-core/tests/test_ai_json_client.py`.
- Media: `procurement_core/ai/stt.py`, `mistral_image_description.py`,
  `ocr/mistral_ocr.py`, `ocr/ollama_vision.py`, and procurement API internal
  STT/image-description routes.
- Existing Stage 1 evidence keeps legacy authoritative and records an
  `AI_ADAPTER=legacy` rollback; schema/latency acceptance is consumer-owned.

This is evidence to extract/compare/generalize, not code to relabel as
canonical AI Core.

### KMO (read-only reference)

Observed at `main@31f6f9b782b4ce7556c23b1e667181d0d6d8e36e`.

- Copied registry: `services/operations-service/config/ai_providers.yaml`.
- Selection/env precedence: `app/modules/ai/provider_config.py`.
- Direct clients: `app/modules/ai/chat_client.py`.
- Retry/fallback: `app/modules/ai/retry.py`, `router.py`, and
  `tests/test_ai_retry.py` / `test_ai_chat.py`.
- Separate media integration:
  `app/modules/image_description/client.py` and `service.py`.

The same provider names, generic `AI_API_KEY` family, and chain shape as
Prozakupki demonstrate lineage. KMO remains an evidence source only; no file was
changed and its old path remains authoritative.

### Zoom

Evidence paths: `backend/pyproject.toml`, `backend/config/ai_providers.yaml`,
`backend/app/modules/ai/runtime.py`, `adapters/raw_ollama.py`,
`adapters/langchain_ollama.py`, and `backend/tests/test_ai_adapter_contract.py`.
The raw adapter rollback and exact `record_llm_result`-compatible v0.1 imports
must survive any additive package work.

### Clin-rec

Evidence paths: `pyproject.toml`, `app/core/llm_factory.py`,
`app/core/ai_runtime.py`, and `tests/test_llm_factory.py`. The product owns
provider order, domain validation, and schema acceptance. Installing the
historical v0.2 dependency bundle would conflict with its LangChain major
constraints.

### Landing Sell

Observed tracked checkout
`docs/operator-site-generation-workflow@5645cd84aee903d547cf5c9e96cb9eef81166382`,
which was dirty; claims here are limited to tracked files.

- Pin: `pyproject.toml:19`.
- Gateway: `ai/gateway.py`; privacy handoff: `ai/envelope.py`.
- Policy: `ai/privacy.py`, `ai/privacy_classifier.py`, and
  `inventories/privacy-class-policies.v0-1.yaml`.
- Contracts: `tests/test_ai_core_gateway.py` and
  `tests/test_t516_privacy_envelope.py`.

Landing Sell is not in `projects.yaml`, but has an accepted compatibility-matrix
exception. It is therefore a real compatibility consumer, not an allowlisted
write target.

### agent-lab

Observed `main@c87b3e987f70323355b78ec16858acabe8ef260e`.
Evidence: `pyproject.toml:12`, `src/agent_lab/ai_core_adapter.py`,
`config/model-aliases.yaml`, and `tests/test_ai_core_adapter.py`. Vendored
`upstream/` repositories were excluded from agent-lab's own consumer evidence.

### Transcription and image-description services

Both clients are present on their respective `origin/main` revisions, not only
in local feature work:

- transcription `origin/main@067a0f2b9441837a4f1897f19de8707992161128`:
  `app/providers/ai_core.py`, `app/config.py`, `app/providers/factory.py`, and
  `tests/unit/test_ai_core_provider.py`;
- image description
  `origin/main@0d6b795af88d09ffd6991679079d1a8377b5d6e8`:
  the analogous files plus `tests/unit/test_processor.py`.

Both factories default to `fake`. Their version-1 HTTP shapes are consumer-side
expectations only. No corresponding route, auth policy, service deployment, or
provider execution exists in `ai-core main`; enabling `ai_core` would therefore
require a separately authorized server and deployment contract.

### Alpha University

Evidence: `PROJECT.yaml`, accepted `docs/adr/ADR-023-ai-core-narrow-boundary.md`,
`docs/integrations/AI_CORE.md`, `src/alpha_university/content_ocr/`, and
`tests/unit/test_content_wp18e_ocr_shadow.py`. Its current OCR is Tesseract,
shadow-only and noncanonical. No `ai-core`, LangChain, Mistral, Ollama, or
OpenAI dependency was found in `pyproject.toml` on the recorded main revision.

## Other inspected repositories/directories

| Entry | Revision/type | Result |
|---|---|---|
| `01_omk_analytics` | directory/symlink, no canonical Git consumer found | no runtime AI evidence from the required term scan |
| `02_landing_sell` | Git | positive; detailed above |
| `1C_Autoconnector` | `master@73f629c…` | no relevant AI integration found |
| `Clin-rec` | Git | positive; allowlisted, detailed above |
| `_benchmarks` | data/artifacts | not a runtime consumer |
| `_blind_trials` | data/artifacts | not a runtime consumer |
| `_senior_handoffs` | local handoff artifacts | not a runtime consumer/source of truth |
| `agent-lab` | Git | positive; detailed above |
| `ai-core` | Git | positive; detailed above |
| `alpha-university` | Git | AI-adjacent; detailed above |
| `image-description-service` | Git | positive HTTP consumer; detailed above |
| `ivd_2student` | `main@c20df9…` | no relevant AI integration found |
| `ivd_sharescreens` | `main@b971101…` | no relevant AI integration found |
| `kmo` | Git | positive; detailed above |
| `mastering-service` | `main@fa5c2e945bd9fbad6b9f0669a82831ba42b3ef7c` | no active AI runtime; boundary test forbids AI SDK imports; future G7 AI is optional only |
| `onprem-processing` | non-Git planning directory | future optional AI gateway only; current design is deterministic/on-prem and must work without external AI |
| `platform-control` | Git | governance owner, not provider runtime |
| `prozakupki-meta` | container directory | canonical nested consumer is `prozakupki-platform`; other worktrees/references not counted twice |
| `transcription-service` | Git | positive HTTP consumer; detailed above |
| `vds-proxy-1` | `master@3ec2e77…` | no relevant AI integration found |
| `zoom-in-plan` | Git | positive; detailed above |

Auxiliary top-level entries were also classified: `README` and `README_kmo`
are files, not projects; `_coord_worktrees` and `_worktrees` contain alternate
checkouts and were not double-counted; `_cursor-standards` is a non-Git
standards directory and not a runtime consumer. These entries were inspected
only to determine inventory scope and were not modified.

No claims are made about repositories outside this enumerated workspace.

## Cross-project compatibility findings

1. There is no single current provider/runtime implementation. `main` tracing,
   v0.2 libraries, consumer-local provider loops, and proposed internal HTTP
   service contracts coexist.
2. Fallback ownership differs intentionally today: ai-core v0.2 for
   Prozakupki's optional adapter/Landing Sell/agent-lab; consumer loops for
   Zoom, Clin-rec, KMO and Prozakupki legacy. A future single owner must be
   introduced per consumer, never nested globally.
3. Provider names are not interchangeable. `ollama`, `ollama_local`,
   `local_gpu_ollama`, and `local_gpu_vision` combine transport, location, and
   product history differently. Generic `ollama` is ambiguous.
4. Capability evidence is model-specific. A provider-level multimodal boolean
   cannot safely authorize OCR, vision, or STT.
5. Credentials are still distributed across consumers. Future canonical
   records may store env **names**, never values; consolidating actual
   credentials needs a service/operations decision and deployment lock.
6. The two media services already encode expected service contracts, but
   current AI Core cannot satisfy them. They must remain on `fake`/old paths.
7. Privacy enforcement is uneven. Landing Sell has the clearest accepted
   fail-closed envelope; other products cannot be presumed to have equivalent
   egress classification merely because they have authentication or tracing.

## Required future compatibility fixtures

The prioritized test inventory is maintained in
`docs/migration/current_state_baseline.md`. Consumer fixtures must contain only
configuration semantics and synthetic data: no product prompts, domain
schemas, production payloads, credentials, or copied workflow code.
