# ai-core consolidation foundation — 2026-09-07

## Status

**Branch:** `feat/ai-core-consolidation-foundation-20260907`  
**Base:** `main` at `7569441c18362cfd15524ad73f56f7f35580c86f`  
**Scope:** additive foundation only; no consumer writes, no release/tag, no production deploy.

This work is explicitly authorized by the user on 2026-09-07 as the first implementation step after the earlier RFC-only phase.

## 1. Repository identity and topology

The canonical repository is **`kkobanenko/ai-core`**. `kkobanenko/prozakupki-platform` is a consumer/reference implementation and must not be mistaken for the canonical repository.

Verified topology on 2026-09-07:

- `ai-core/main` = `7569441c18362cfd15524ad73f56f7f35580c86f`.
- `feat/provider-catalog-privacy-routing` = `679b88fa7cd6e9f64b543c405a90b2ef0dcdc575`.
- The two lines diverged from merge base `92828dc043a2629d9d0b13dc9e6f080b0cf95088`.
- Provider branch is 14 commits ahead / 10 behind main.
- Therefore the old provider branch must **not** be mechanically merged into main. Consolidation is selective and compatibility-first.

## 2. Source-of-truth inventory

### Canonical ai-core main

Owns the current stable tracing/public compatibility surface:

- Phoenix/OpenTelemetry tracing bootstrap.
- `AttributeValue` / `sanitize_attributes`.
- `record_llm_result`.
- `start_llm_span`, `init_tracing`, `shutdown_tracing`.
- Dependency-light installation (only Phoenix runtime dependency on main before this branch).

### Historical provider/multimodal line

`feat/provider-catalog-privacy-routing` / v0.2.x contains reusable, already-tested ideas:

- canonical provider identities;
- model-specific capabilities;
- fail-closed privacy routing;
- provider health isolation;
- structured JSON client/provider factory;
- single-provider vision and PDF OCR primitives;
- safe trace attributes and surrogate/DLP helpers.

These are evidence and code sources for selective reconciliation, not a merge target.

### Prozakupki

`kkobanenko/prozakupki-platform` currently contains the most operationally advanced bounded-inference implementation:

- `config/ai_providers.yaml` with OpenAI, Mistral, Ollama local/cloud, local GPU, Whisper, fake and vision identities;
- structured JSON fallback;
- STT routing;
- image-description routing;
- explicit cloud opt-in for image description;
- shared request deadline / local attempt reserve behavior.

It remains read-only during ai-core consolidation. Working behavior should be extracted into canonical contracts rather than copied again.

### KMO

KMO README explicitly states that its AI provider registry was copied from Prozakupki and its failover is `local_gpu_ollama -> ollama_cloud -> mistral`. That is direct duplication and a future migration target. KMO is read-only during this foundation step.

### transcription-service

The service owns asynchronous transcription workflow concerns: authenticated API, PostgreSQL durable jobs, worker, media/chunking and result assembly. Its `AiCoreTranscriptionProvider` is intentionally a thin client of an internal AI-core STT contract. Therefore chunking, job retries, persistence and artifact semantics do **not** belong in canonical ai-core.

### image-description-service

The service explicitly declares the intended boundary:

- image service owns upload/storage, normalization, durable queue/job retry and artifacts;
- AI-core owns bounded inference and provider routing;
- image service provider adapter knows only AI-core base URL/service key/timeout.

This is the strongest existing evidence for the reusable service boundary.

### Alpha-University

Current main status still declares the planner `DETERMINISTIC / AI-INDEPENDENT`. Alpha work remains a consumer-side/reference concern; this foundation does not change Alpha and does not assume live inference where the repository status does not establish it.

## 3. Canonical ownership decision

### ai-core should own

1. Provider identity and canonical aliases.
2. Model/provider capability metadata.
3. Network/privacy eligibility and fail-closed external-egress policy.
4. Credential **environment variable names** and endpoint resolution contracts; never secret values in catalog metadata.
5. Normalized bounded-inference errors.
6. Provider health isolated by provider identity.
7. Retry/fallback for one bounded inference request, with one clear fallback owner.
8. Metadata-only tracing hooks that preserve the existing tracing API.
9. Optional transport implementations behind extras; tracing-only install must remain lightweight.
10. Small HTTP service adapters/contracts where reusable async services need a network boundary.

### ai-core should not own

- domain prompts/business validation;
- durable job queues;
- PostgreSQL job state;
- media storage;
- transcription chunking/rebasing;
- image normalization/EXIF stripping;
- product-specific rights or consent rules;
- workflow orchestration across multiple business steps;
- consumer database entities.

## 4. Foundation implemented on this branch

Additive modules ported from the proven provider line, reconciled onto current main:

- `src/ai_core/provider_catalog.py`
- `src/ai_core/capabilities.py`
- `src/ai_core/privacy.py`
- policy APIs exposed through their submodules; root `ai_core.__all__` remains exactly v0.1-compatible
- `tests/test_provider_policy_foundation.py`

Properties of this slice:

- no LangChain dependency;
- no httpx dependency;
- no change to `pyproject.toml`;
- current tracing exports and exact root `__all__` are preserved;
- provider catalog stores env names, not credential values;
- unknown model capabilities fail closed;
- `SECRET + RAW` is always blocked;
- sensitive RAW is denied for external cloud and unknown network boundaries;
- sanitized/surrogated sensitive data can be eligible only when provider policy explicitly allows it.

## 5. Model drift intentionally not hidden

The v0.2.2 capability registry contains older proven model identifiers (`qwen3.5:9b`, `qwen2.5vl:7b`). Prozakupki main currently demonstrates newer operational identifiers such as `qwen3.6:35b`, `qwen3-vl:4b` and `local_gpu_whisper`/faster-whisper.

This branch intentionally does **not** silently replace the old proven model registry. The next slice must add current models only after defining how model evidence/versioning is represented, so capability declarations do not become an unreviewed mutable list.

## 6. Next implementation slices

### C2 — provider/model evidence reconciliation

- canonical alias mapping for Prozakupki/KMO names;
- explicit current model profiles;
- add STT capability/provider identity without conflating it with chat Ollama;
- document evidence/provenance for each capability.

### C3 — bounded routing contracts

- dependency-light provider health state;
- normalized error taxonomy;
- deterministic eligible-provider ordering;
- fail-closed RAW exhaustion;
- shared request deadline and bounded attempt budget;
- no nested fallback owners.

### C4 — optional transports

- tracing base install remains lightweight;
- provider transports move behind optional extras;
- reconcile structured JSON client with current main compatibility API;
- then add vision/OCR/STT adapters using the same contracts.

### C5 — HTTP service boundary

Define the canonical internal inference API used by `transcription-service` and `image-description-service`, then move the existing Prozakupki-owned bounded inference endpoints toward this canonical runtime without changing those consumers until contract tests are green.

## 7. Merge gate for this branch

Before merge:

1. Existing main tests must stay green.
2. New provider-policy tests must pass on Python 3.10+.
3. Diff must show no `pyproject.toml` dependency expansion.
4. Public v0.1-shaped tracing API contract must remain intact, including exact root `__all__`.
5. No consumer repository is modified by this branch.
