# AI Core PR #3-#5 Paper Decomposition Plan

**Date:** 2026-09-09
**Status:** documentation-only proposal
**Branch mutation:** forbidden in this package

This plan maps existing draft content into future review units. It does not
rewrite history, update PR metadata, authorize merge, or accept any governance
decision. Decision IDs refer to
`docs/governance/2026-09-09-ai-core-decision-packets.md`.

## 1. Disposition vocabulary

| Disposition | Meaning |
|---|---|
| `FOUNDATION_CANDIDATE` | Small dependency-light block potentially eligible after named decisions and fresh review. Not merge authorization. |
| `FIX_BEFORE_FOUNDATION` | Concept fits foundation, but current behavior/evidence/API must be corrected first. |
| `SEPARATE_GOVERNED_WP` | Valuable block requiring its own explicit governance decision and package. |
| `DEFER_TO_RUNTIME` | Belongs only after contracts and runtime scope are authorized. |
| `REJECT_REDESIGN` | Current behavior conflicts with safety/compatibility boundary; do not carry it forward. |

## 2. Pinned PR state

| PR | Base | Head | State on 2026-09-09 | Governance gate |
|---|---|---|---|---|
| #3 | `main@7569441...` | `4e26d67b825194e489a6a8b553c2a53dfea2a81f` | OPEN, DRAFT, CI green, no approval | platform-control #293 OPEN |
| #4 | PR #3 head | `1b2569a612968a3ac5099dea955cfccdcb191d52` | OPEN, DRAFT, CI green, no approval | platform-control #291 OPEN |
| #5 | PR #3 head | `25c269bb93dd37bd9b1556051972f5e1e60b34ad` | OPEN, DRAFT, CI green, no approval | platform-control #292 OPEN |

Heads and bases are evidence pins, not instructions to rebase or merge.

## 3. PR #3 — consolidation foundation

Changed files: handoff, `capabilities.py`, `privacy.py`,
`provider_catalog.py`, and `test_provider_policy_foundation.py`.

| Logical block / exact symbols | Disposition | Decisions | Required change / reason |
|---|---|---|---|
| Preserve existing root `ai_core.__all__`; expose new APIs only from submodules | `FOUNDATION_CANDIDATE` | D1 | Retain exact nine-symbol root contract and import-isolation tests. |
| `NetworkBoundary`, `PiiPolicy`, `BackendKind`, `HealthProbeKind`, `CostClass`, `LatencyClass` | `FOUNDATION_CANDIDATE` | D1, D3 | Keep dependency-light types; review whether cost/latency/health belong in first minimal slice. |
| Four constants and `CANONICAL_PROVIDER_IDS` | `FOUNDATION_CANDIDATE` | D1, D3 | Only accepted four IDs; no aliases/new identities. |
| `ProviderProfile`, `get_provider_catalog`, `get_provider_profile` | `FIX_BEFORE_FOUNDATION` | D1, D3, D4 | Separate identity/security metadata from behavioral priority and unproven capability booleans. Unknown ID stays fail-closed. |
| Endpoint/credential environment-variable names, default schemes/ports | `SEPARATE_GOVERNED_WP` | D3, D6a, D6b | Operational endpoint/credential resolution crosses runtime/service boundary; retain names as evidence, not first foundation behavior. |
| `ProviderCapability`, `ProviderModelProfile`, fail-closed lookup helpers | `FOUNDATION_CANDIDATE` | D1, D3 | Keep types/helpers; concrete routing eligibility must use accepted evidence semantics. |
| Four concrete `_MODEL_PROFILES` | `FIX_BEFORE_FOUNDATION` | D3, D6a | Attach exact evidence level/boundary; GPU vision 503 cannot promote capability. Consider shipping no concrete profiles in minimal slice. |
| `DataClass`, `OutboundForm`, sensitivity helpers | `FOUNDATION_CANDIDATE` | D1, D2 | Retain only with explicit all-form SECRET tests. |
| `is_eligible_for_outbound`: `SECRET + RAW` denial | `FIX_BEFORE_FOUNDATION` | D2 | Generalize denial to every outbound form and network boundary. |
| `is_eligible_for_outbound`: sanitized/surrogated SECRET eligibility | `REJECT_REDESIGN` | D2 | Violates zero-route/zero-attempt invariant. |
| Provider-level `raw_pii_policy` / `sanitized_pii_policy` as sufficient egress authority | `REJECT_REDESIGN` | D2 | Request-level authorization must be explicit; catalog policy alone cannot authorize egress. |
| Foundation tests for four IDs, secret-free metadata, unknown model, root compatibility | `FOUNDATION_CANDIDATE` | D1-D3 | Retain and add all-form SECRET/request-egress cases. |
| Existing PR handoff claims | `FIX_BEFORE_FOUNDATION` | D1-D3 | Remove implementation-authorized wording; link recorded governance decisions and corrected evidence. |

### Proposed future PR #3 slice

Minimal contents after decisions: root compatibility test; dependency-light
identity/privacy/capability types; accepted four IDs; fail-closed unknown lookup;
all-form SECRET and explicit-egress contract. Exclude concrete transports,
service, endpoint resolution, global priority, health behavior, new identities,
STT, and executor.

## 4. PR #4 — provider aliases and evidence

Changed files: handoff, modifications to `capabilities.py` and
`provider_catalog.py`, new `provider_aliases.py`, and two test files.

| Logical block / exact symbols | Disposition | Decisions | Required change / reason |
|---|---|---|---|
| `ProviderAliasError`, `UnknownProviderAliasError`, `AmbiguousProviderAliasError` | `FOUNDATION_CANDIDATE` | D1, D3 | Dependency-light fail-closed error types. |
| `resolve_provider_id` normalization and generic `ollama` ambiguity rejection | `FOUNDATION_CANDIDATE` | D3 | Retain only when output is accepted ID and request context cannot be guessed. |
| Aliases to accepted IDs: `ollama_local`, `local_gpu_ollama`, `local_gpu_vision`, `mistral`, `mistral_ocr` | `FIX_BEFORE_FOUNDATION` | D3, D6a | Document identity-only meaning; alias must not imply model capability or trusted GPU boundary. |
| Aliases to `gpu_whisper`, `openai_external`, `deepseek_external` | `SEPARATE_GOVERNED_WP` | D3, D6a | Outputs are unaccepted identities. |
| New provider IDs `gpu_whisper`, `openai_external`, `deepseek_external` | `SEPARATE_GOVERNED_WP` | D3, D6a, D6b | Separate approval, credentials, boundary, ownership, and rollback required. |
| `OPENAI_COMPATIBLE`, `FASTER_WHISPER_HTTP` backend kinds | `SEPARATE_GOVERNED_WP` | D3, D6b | Transport-family expansion is not needed by minimal four-ID foundation. |
| `STT_SEGMENTS` enum and STT profiles | `SEPARATE_GOVERNED_WP` | D3, D6b | Capability, data handling, model evidence, and service ownership remain OPEN. |
| Two-level `ModelEvidenceLevel` (`HISTORICAL_PROVEN`, `CURRENT_OBSERVED`) | `REJECT_REDESIGN` | D3 | Conflates config, unit, integration, and runtime evidence. Replace with D3 levels. |
| Consumer-config-only profiles labelled `CURRENT_OBSERVED` | `REJECT_REDESIGN` | D3 | Configuration is `CONFIGURED`, not runtime capability proof. |
| Mistral OCR profile | `SEPARATE_GOVERNED_WP` | D3 | Live success is useful exact-path evidence, but capability acceptance remains separate. |
| `qwen3-vl:4b` GPU vision profile | `SEPARATE_GOVERNED_WP` | D3, D6a | Normalization/reachability confirmed; HTTP 503 is `FAILED_INCONCLUSIVE`, not promotion. |
| Alias/evidence tests | `FIX_BEFORE_FOUNDATION` | D3 | Split accepted-ID alias tests from new-identity/STT tests; assert evidence levels precisely. |
| Existing PR handoff claims | `FIX_BEFORE_FOUNDATION` | D3 | Replace `CURRENT_OBSERVED` ambiguity and distinguish consumer config from runtime proof. |

### Proposed future PR #4 slices

1. Accepted-ID alias/error slice after D3.
2. Evidence vocabulary and registry mechanics after D3, without unaccepted
   production routes.
3. One separate governed package per identity family/capability; STT never rides
   implicitly with alias mechanics.

## 5. PR #5 — bounded routing contracts

Changed files: handoff, `budget.py`, `errors.py`, `health.py`, `routing.py`, and
`test_bounded_routing_contract.py`.

| Logical block / exact symbols | Disposition | Decisions | Required change / reason |
|---|---|---|---|
| `AttemptBudget.from_timeout`, `remaining_seconds`, validation | `FOUNDATION_CANDIDATE` | D5 | Pure monotonic arithmetic; no sleep/network/execution. |
| `timeout_for_attempt` reserve calculation | `FIX_BEFORE_FOUNDATION` | D4, D5 | Retain after deadline semantics define backoff/service overhead and reserve ownership. |
| `AiErrorKind`, `ErrorDescriptor` structure | `FIX_BEFORE_FOUNDATION` | D4, D5 | Add policy/privacy, capability, schema/contract, request-invalid semantics; keep retry and fallback flags distinct. |
| `_status_code` and `classify_provider_error` class-name heuristics | `REJECT_REDESIGN` | D5 | Canonical adapters need explicit mapping; heuristics may be compatibility evidence only. |
| `RawRouteExhaustedError`, `NoEligibleProviderError`, `RequestDeadlineExceededError` | `FIX_BEFORE_FOUNDATION` | D2, D5 | Align names/payload-free messages with accepted taxonomy and all-form SECRET. |
| `HealthTarget` and provider/model isolation | `FOUNDATION_CANDIDATE` | D4 | Pure keying/state concept; no network probe. |
| `ProviderHealthStatus` vocabulary | `FIX_BEFORE_FOUNDATION` | D3-D5 | Separate reachability, runtime capability evidence, quota, auth, and model absence without automatic route promotion. |
| `ProviderHealthStore.is_healthy`: `UNKNOWN` returns true | `REJECT_REDESIGN` | D4 | Normal automatic production routes must fail closed; exploration requires explicit opt-in. |
| `RouteCandidate`, `RejectedCandidate`, `RoutePlan` data shapes | `FOUNDATION_CANDIDATE` | D2-D4 | Pure planning result candidates after accepted field/ordering design. |
| `PrivacyAwareRouter._authorized_ids`: missing allowlist means full catalog | `REJECT_REDESIGN` | D2 | Missing request egress authorization cannot enable providers. |
| `PrivacyAwareRouter.plan`: inherited transformed SECRET eligibility | `REJECT_REDESIGN` | D2 | Apply all-form SECRET denial before provider lookup/attempt planning. |
| `PrivacyAwareRouter.plan`: global `priority_hint` sort | `REJECT_REDESIGN` | D4 | Preserve explicit request order; lexical tie-break only inside equal rank. |
| Capability/health filtering and rejection audit concept | `FIX_BEFORE_FOUNDATION` | D3, D4 | Consume accepted evidence and fail-closed unknown health; keep rejection reasons metadata-only. |
| Error/health/routing/deadline tests | `FIX_BEFORE_FOUNDATION` | D2-D5 | Split pure contracts; invert fail-open assertions; add three-layer retry ownership cases. |
| Any future transport, sleep, provider call, retry loop, or fallback executor | `DEFER_TO_RUNTIME` | D4-D6 | Not present in PR; explicitly exclude from contract package. |
| Existing PR handoff claims | `FIX_BEFORE_FOUNDATION` | D2-D5 | Remove claim that current planner already conforms to accepted privacy/fallback target. |

### Proposed future PR #5 slices

1. Pure canonical error descriptors and deadline arithmetic after D5.
2. Provider/model health state after D3/D4, with unknown fail-closed default.
3. Deterministic route-plan data/filtering after D2-D4.
4. Execution/retry/fallback only in later runtime-authorized package.

## 6. Future sequence and gates

| Sequence | Future package | Prerequisites | Intended base | Required validation | Stop condition / rollback |
|---|---|---|---|---|---|
| S0 | Platform-control decision records and pointer reconciliation | Operator choices D1-D6 | Fresh platform-control main | governance review, exact SHA checks | Stop if any decision remains ambiguous; revert governance-only commit if rejected. |
| S1 | Minimal AI Core foundation | Accepted D1-D3; issues #293/#291 disposition | Fresh `ai-core/main` | exact root API, Python 3.10/3.12, all-form SECRET, no dependency expansion | Close/drop future branch; main/consumers unchanged. |
| S2 | Evidence and accepted-ID alias contracts | Accepted D3; S1 | Accepted S1 head | evidence-level tests, alias ambiguity, no new IDs/STT | Drop slice without changing S1. |
| S3 | Error/deadline/health/route-plan contracts | Accepted D2-D5; S1/S2 as applicable | Reviewed foundation head | privacy matrix, explicit egress, order, unknown health, error/deadline tests | Drop slice; no executor or consumer effects. |
| S4 | HTTP service contract design | Accepted D6b only | Documentation base chosen by operator | threat model, auth/ownership/schema compatibility review | Design rejection changes no runtime. |
| S5 | GPU boundary evidence package | D6a investigation authorization and deployment lock if operational action needed | Platform-control-selected base | ownership/network/auth/logging/probe evidence | Retain `UNKNOWN_BOUNDARY`; no route promotion. |
| S6 | Runtime implementation | Separate explicit runtime authorization plus relevant accepted decisions | Operator-selected reviewed contract head | transport/integration/security/consumer compatibility gates | Runtime-specific rollback plan required before start. |

## 7. Mechanical rules for any later branch work

- Start from freshly verified intended base; never assume current draft stack is
  safe to rebase or merge.
- Copy/cherry-pick only reviewer-approved logical blocks, not whole draft commits.
- Preserve PR #3-#5 as immutable evidence until operator authorizes branch work.
- One future PR carries one approval boundary; new identities and STT do not
  share implicit approval with foundation.
- No merge while required decision ID is `OPEN`.
- No runtime, consumer, release, deployment, or tag action follows from this
  decomposition document.

All decomposition labels are recommendations. No PR branch, metadata, or history
was changed by this package.
