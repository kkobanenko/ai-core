# AI Core S1 Foundation Contracts Design

**Date:** 2026-09-11
**Status:** approved by authoritative platform-control governance and operator continuation

## Goal

Add dependency-light, pure contracts for governed provider identities,
model-scoped capability evidence, and privacy/egress eligibility without
changing the existing root API or adding any runtime behavior.

## Authoritative boundary

The source of truth is platform-control ADR-022 plus the S1-start decision on
`platform-control/main@c78b5e735d9b47e6550f2f6f7df084406c3ecfe0`.
Only `S1_foundation_contracts` is authorized. The broad implementation flag
remains false.

The accepted provider IDs are exactly:

- `vm100_local_ollama`
- `gpu_ollama`
- `ollama_cloud`
- `mistral_external`

Runtime, service, transports, provider calls, executor, retry/fallback
execution, consumer migration, aliases, route planning, health behavior,
deadline execution, new provider identities, `STT_SEGMENTS`, GPU trust
promotion, infrastructure/deployment, release, and tag work are excluded.

## Approaches considered

### 1. Minimal separated contracts — selected

Use three focused standard-library-only modules: identity catalog, capability
evidence, and privacy/egress. Expose them only through explicit submodule
imports. This keeps the tracing root isolated and each policy boundary
independently testable.

### 2. Adapt PR #3 wholesale — rejected

PR #3 mixes identity metadata with backend kinds, endpoint and credential
environment names, health probes, cost/latency, global priority, and unproven
capability booleans. Its transformed-SECRET behavior also conflicts with
ADR-022. Carrying the whole block would exceed S1 and weaken fail-closed
semantics.

### 3. One monolithic policy module — rejected

A single module would couple identity, evidence, and egress decisions, making
future S2/S3 review boundaries unclear and increasing accidental imports into
the tracing surface.

## Module design

### `ai_core.provider_catalog`

Defines:

- `NetworkBoundary`: `LOCAL_SAME_HOST`, `EXTERNAL`, `UNKNOWN_BOUNDARY`;
- four canonical provider constants and `CANONICAL_PROVIDER_IDS` in governance
  order;
- immutable `ProviderIdentity(provider_id, network_boundary)`;
- `UnknownProviderIdentityError`, a fail-closed lookup error;
- `get_provider_catalog()` returning a read-only mapping;
- `get_provider_identity(provider_id)` returning the known identity or raising
  the explicit error.

The catalog contains identity and trust-boundary metadata only. It contains no
endpoint, credential, backend, health, cost, latency, priority, model, or
capability fields. `gpu_ollama` is `UNKNOWN_BOUNDARY`.

### `ai_core.capabilities`

Defines pure vocabulary:

- `ProviderCapability`: text, structured JSON, vision image, and OCR PDF;
- `CapabilityEvidenceLevel`: `CONFIGURED`, `UNIT_TESTED`,
  `INTEGRATION_TESTED`, `RUNTIME_OBSERVED`, `FAILED_INCONCLUSIVE`;
- immutable `CapabilityEvidence` whose subject is provider identity, model,
  capability, and network boundary;
- `has_runtime_observation(evidence)` which is true only for
  `RUNTIME_OBSERVED` and explicitly does not imply routing eligibility.

Construction fails closed for unknown provider IDs and boundary mismatch.
There is no concrete model registry and no runtime capability claim.
`STT_SEGMENTS` is absent.

### `ai_core.privacy`

Defines:

- `DataClass`: synthetic, public no PII, public possible PII, private client
  data, and secret;
- `OutboundForm`: raw, sanitized, and surrogated;
- `is_egress_eligible(...)` as a pure pre-routing decision.

Rules:

1. `SECRET` is denied for every outbound form and every governed boundary.
2. Transformation changes outbound form, never the original data class.
3. Non-secret external and unknown-boundary egress requires explicit
   request-level authorization.
4. Local-same-host non-secret data is eligible without external egress
   authorization.
5. Catalog membership cannot grant egress because the decision consumes the
   request classification, form, boundary, and explicit authorization only.

## Compatibility

`ai_core.__all__` remains the exact existing nine-symbol tuple/list contract.
The new modules are not imported from package root. Current tracing imports do
not load any foundation submodule. No dependency is added to `pyproject.toml`.

## Testing

Tests prove:

- exact provider set and fail-closed lookup;
- immutable, metadata-minimal identities and unknown GPU boundary;
- exact evidence vocabulary and subject validation;
- failed/inconclusive evidence never counts as runtime observation;
- the complete 3 outbound forms × 3 boundaries SECRET denial matrix;
- fail-closed external/unknown egress when authorization is missing;
- root API and tracing import isolation;
- absence of aliases, new provider IDs, credentials, and STT vocabulary;
- all pre-existing tests remain green.

Python 3.10 is verified locally. Python 3.12 is delegated to hosted CI if the
local executable is unavailable.

## Provenance

PR #3 is used only as read-only design evidence for the useful separation of
provider constants, capability vocabulary, privacy vocabulary, and fail-closed
lookup. Code is implemented test-first. Endpoint/credential metadata, concrete
profiles, global priority, provider-level egress authority, and transformed
SECRET eligibility are explicitly excluded or redesigned.

## Rollback

Before merge, close the future draft S1 PR and drop its branch/worktree. No
main, consumer, runtime, deployment, release, or tag rollback is required.
