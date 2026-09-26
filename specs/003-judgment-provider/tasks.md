# Tasks: Provider-Neutral Judgment Contract

**Feature**: `003-judgment-provider`

**Authority**: `spec.md` + `plan.md`

**Package type**: This file plans a future, separately authorized J1 implementation. The current package is docs-only.

**Execution rule**: Every task below requires the J1 opening human gate. Tests are written before their corresponding implementation. A STOP outcome is evidence, not a PASS.

## Phase 1 — Opening Gate and Test Contracts

- [ ] T001 [US1] Record the authorized J1 base and contract inventory in the future J1 PR description before editing `src/ai_core/**`.
  - **Inputs**: `specs/003-judgment-provider/spec.md`, `specs/003-judgment-provider/plan.md`, operator `AUTHORIZE_J1`, platform-control review reference, exact ai-core base SHA.
  - **Changed surfaces**: PR evidence only; no repository file.
  - **Deterministic acceptance**: The PR evidence names the exact base SHA, contract-only scope, runtime files allowed by later tasks, `NO_REAL_PROVIDER_CALLS`, and J2 exclusions.
  - **STOP**: Stop before code edits if authorization, review reference, exact base, or scope is absent or contradictory.

- [ ] T002 [P] [US1] Add failing typed-contract tests for request, `Choice`, `Score`, and `Noul` behavior in `tests/test_judgment_contract.py`.
  - **Inputs**: Spec sections “Typed Input,” “Typed Output,” and “Validation Behavior.”
  - **Changed surfaces**: `tests/test_judgment_contract.py`.
  - **Deterministic acceptance**: Tests cover all three valid variants plus empty IDs, duplicate choice keys, invalid score bounds, boolean/non-finite/out-of-range scores, undeclared keys/reasons, invalid confidence, multiple variants, metadata mismatch, and unknown response fields; tests fail only because J1 implementation symbols are absent.
  - **STOP**: Stop if a test requires provider-specific JSON, text parsing, a real SDK, network access, or an unresolved output semantic.

- [ ] T003 [P] [US2] Add failing pre-transport privacy and no-egress tests in `tests/test_judgment_privacy.py`.
  - **Inputs**: Spec sections “Privacy and Egress” and “Fail-Neutral / Fail-Closed Matrix”; existing `src/ai_core/privacy.py`.
  - **Changed surfaces**: `tests/test_judgment_privacy.py`.
  - **Deterministic acceptance**: Fake transport call count is zero for `SECRET`, denied egress, hosted payloads without PUBLIC/contractually confirmed ANONYMIZED status, and local/no-egress hosted fallback; sanitization/surrogation does not manufacture anonymization; missing ZDR evidence remains false/unknown.
  - **STOP**: Stop if passing the tests would require weakening current privacy semantics, adding credentials, or making a real network call.

- [ ] T004 [P] [US2] Add failing shared-deadline, retry, and fallback tests in `tests/test_judgment_deadline.py`.
  - **Inputs**: Spec sections “Provider-Neutral Error Taxonomy” and “Deadline, Retry, and Fallback Semantics”; existing `src/ai_core/budget.py`.
  - **Changed surfaces**: `tests/test_judgment_deadline.py`.
  - **Deterministic acceptance**: A fake clock proves one total deadline, retry range `0..1`, retry only for `RATE_LIMIT`/`TIMEOUT`, no attempt without safe remaining budget, deterministic fallback order, complete gate re-evaluation, and no nested fallback.
  - **STOP**: Stop if a retry or fallback can extend the deadline, bypass a gate, or transfer ownership to a provider adapter.

- [ ] T005 [P] [US1] Add failing strict serialization tests in `tests/test_judgment_serialization.py`.
  - **Inputs**: Typed fields and validation rules in `spec.md`.
  - **Changed surfaces**: `tests/test_judgment_serialization.py`.
  - **Deterministic acceptance**: Valid requests/results round-trip exactly; unknown/missing fields, wrong primitive types, wildcard versions, `*-latest`, non-finite values, case folding, whitespace normalization, and alias guessing are rejected.
  - **STOP**: Stop if serialization requires a new dependency, provider wire schema, or permissive unknown-field behavior.

- [ ] T006 [P] [US2] Add failing telemetry and authority tests in `tests/test_judgment_telemetry.py` and `tests/test_judgment_authority.py`.
  - **Inputs**: Spec sections “Metadata-Only Telemetry,” “Authority Limits,” and the failure matrix.
  - **Changed surfaces**: `tests/test_judgment_telemetry.py`, `tests/test_judgment_authority.py`.
  - **Deterministic acceptance**: Default telemetry contains only allowlisted metadata and excludes all payload/result values; every matrix row preserves its specified baseline or human gate for error, timeout, invalid response, missing confidence, and below-threshold confidence.
  - **STOP**: Stop if a model result can authorize merge, destructive permission, access, egress, legal/business acceptance, or completion.

## Phase 2 — Typed Values and Errors

- [ ] T007 [US1] Implement immutable judgment request/result values and validation in `src/ai_core/judgment_models.py`.
  - **Inputs**: T002 and T005 tests; exact typed fields from `spec.md`.
  - **Changed surfaces**: `src/ai_core/judgment_models.py`.
  - **Deterministic acceptance**: T002 and T005 pass; exactly one of `Choice`, `Score`, or `Noul` is accepted; invalid values fail before provider invocation; decision-pack ownership and thresholds are not encoded in ai-core.
  - **STOP**: Stop if implementation requires reflection, inheritance, dynamic field generation, provider-specific response classes, or a new dependency.

- [ ] T008 [P] [US1] Implement normalized judgment error values in `src/ai_core/judgment_errors.py`.
  - **Inputs**: Error taxonomy in `spec.md`; existing `src/ai_core/errors.py` vocabulary.
  - **Changed surfaces**: `src/ai_core/judgment_errors.py`.
  - **Deterministic acceptance**: Every specified error kind has exact retry/fallback flags; error serialization contains metadata only; `RATE_LIMIT` and `TIMEOUT` are the only same-provider retryable kinds; unknown errors are terminal.
  - **STOP**: Stop if raw exceptions, credentials, request payloads, or provider responses would be exposed.

## Phase 3 — Capability and Provider Boundary

- [ ] T009 [US3] Add the separately authorized future `JUDGMENT` capability and exact regression tests in `src/ai_core/capabilities.py` and `tests/test_s1_capability_evidence.py`.
  - **Inputs**: D7 catalog integration requirements; T001 authorization evidence; current capability evidence contract.
  - **Changed surfaces**: `src/ai_core/capabilities.py`, `tests/test_s1_capability_evidence.py`.
  - **Deterministic acceptance**: `JUDGMENT` exists only as explicit capability vocabulary; evidence alone still grants no routing/admission authority; existing capabilities remain unchanged; no D7 pending identity or `STT_SEGMENTS` implementation is bundled.
  - **STOP**: Stop if J1 authorization does not explicitly cover the enum change, if catalog admission would become implicit, or if issue `#291` implementation is pulled into J1.

- [ ] T010 [US1] Implement the separate provider-neutral invocation boundary in `src/ai_core/judgment_provider.py`.
  - **Inputs**: T002 tests; `src/ai_core/judgment_models.py`; `src/ai_core/judgment_errors.py`.
  - **Changed surfaces**: `src/ai_core/judgment_provider.py`, `tests/test_judgment_contract.py`.
  - **Deterministic acceptance**: One invocation accepts one typed request and returns one validated typed result or normalized error; text/chat providers cannot satisfy the contract accidentally; no provider-specific wire field is public.
  - **STOP**: Stop if the interface becomes a JSON/text-generation mode, uses inheritance-based provider hierarchies, or needs a real adapter.

- [ ] T011 [US3] Implement explicit future judgment eligibility records without provider admission in `src/ai_core/judgment_policy.py`.
  - **Inputs**: T009 `JUDGMENT`; existing provider identity, capability evidence, privacy, health, and routing contracts.
  - **Changed surfaces**: `src/ai_core/judgment_policy.py`, `tests/test_judgment_contract.py`.
  - **Deterministic acceptance**: Selection requires exact provider identity, `JUDGMENT`, model/version, admission evidence, privacy, egress, and health gates; capability evidence alone is insufficient; pending D7 extensions remain unavailable until separately implemented.
  - **STOP**: Stop if identity implies capability/admission, generic `ollama` resolves, or thresholds enter ai-core policy.

## Phase 4 — Bounded Execution and Deterministic Mock

- [ ] T012 [US2] Implement one-deadline policy orchestration in `src/ai_core/judgment_policy.py`.
  - **Inputs**: T003 and T004 tests; `src/ai_core/budget.py`; `src/ai_core/privacy.py`; normalized judgment errors.
  - **Changed surfaces**: `src/ai_core/judgment_policy.py`, `tests/test_judgment_privacy.py`, `tests/test_judgment_deadline.py`.
  - **Deterministic acceptance**: T003 and T004 pass; all gates run before transport; retry is bounded to one and only for allowed errors; every fallback is re-gated; local/no-egress never reaches hosted candidates; deadline exhaustion stops all attempts.
  - **STOP**: Stop if existing runtime must be weakened, nested fallback appears, or any attempt can outlive the total deadline.

- [ ] T013 [P] [US1] Implement deterministic test-only `mock_judgment` in `src/ai_core/mock_judgment.py`.
  - **Inputs**: `JudgmentProvider` contract and typed values; no external fixtures.
  - **Changed surfaces**: `src/ai_core/mock_judgment.py`, `tests/test_judgment_contract.py`.
  - **Deterministic acceptance**: The mock returns configured typed results/errors with no network, credential, clock, random, or environment dependency; it is clearly test-only and has no production admission path.
  - **STOP**: Stop if the mock requires runtime provider registration, external state, or can be selected as a production provider.

- [ ] T014 [US2] Implement metadata-only judgment telemetry in the smallest separately reviewed surface under `src/ai_core/` and complete `tests/test_judgment_telemetry.py`.
  - **Inputs**: T006 telemetry tests; existing `src/ai_core/tracing.py` and `src/ai_core/attributes.py`.
  - **Changed surfaces**: Prefer `src/ai_core/judgment_provider.py`; modify `src/ai_core/tracing.py` only if exact-head review approves the minimal change; `tests/test_judgment_telemetry.py`.
  - **Deterministic acceptance**: T006 telemetry tests pass; metadata allowlist is exact; payload/result fields remain absent by default; telemetry failure cannot alter the result or failure mode.
  - **STOP**: Stop before changing shared tracing if a judgment-local wrapper is sufficient, or if platform-control tracing review is missing.

## Phase 5 — Integration, Regression, and Human Review

- [ ] T015 [US1] Run focused J1 contract checks and record exact commands/results in the future J1 PR.
  - **Inputs**: T002–T014 implementation head.
  - **Changed surfaces**: PR evidence only; no repository file.
  - **Deterministic acceptance**: Focused tests for contract, privacy, deadline, serialization, telemetry, and authority all pass; failures are reported as failures, not relabelled.
  - **STOP**: Stop J1 closing if any focused check fails or is unavailable without an explained blocker.

- [ ] T016 [US3] Run full regression and docs/static checks and verify the exact J1 diff.
  - **Inputs**: Focused tests passing; repository-supported test and lint commands.
  - **Changed surfaces**: PR evidence only; no repository file.
  - **Deterministic acceptance**: Full existing tests pass; `git diff --check` passes; changed-file inventory contains only J1-authorized surfaces; dependencies, adapters, credentials, consumers, deployment, release, and tags are unchanged.
  - **STOP**: Stop if a regression appears, a non-authorized file changes, or verification depends on live provider traffic.

- [ ] T017 [US2] Obtain exact-head contract and privacy/security review for the future J1 PR.
  - **Inputs**: Exact J1 head SHA; T015/T016 results; risk register and rollback from `plan.md`.
  - **Changed surfaces**: Review evidence only; no repository file.
  - **Deterministic acceptance**: Human review explicitly accepts typed validation, pre-transport privacy, hosted-data rules, no-egress fallback prohibition, deadline/retry semantics, telemetry allowlist, authority limits, and exact changed surfaces.
  - **STOP**: Stop if review targets a stale SHA, leaves a required gate unresolved, or requests a new architecture decision without operator resolution.

- [ ] T018 [US3] Request a separate release decision without creating a release or tag.
  - **Inputs**: Accepted exact J1 head and all closing evidence.
  - **Changed surfaces**: Governance decision record only; no automatic repository mutation.
  - **Deterministic acceptance**: The outcome is explicitly one of hold, revise, or separately authorize release; it does not imply adapter, provider admission, consumer rollout, deployment, release, or tag.
  - **STOP**: Stop after recording the decision; no release action occurs under J1 implementation authorization alone.

## J2 and Later — Explicitly Excluded from J1

The following are separate work packages and MUST NOT be folded into any task above:

- `typesafe_jev` adapter, SDK, credentials, endpoint, or real network integration;
- `kev_local` adapter or network-capable stub;
- provider-specific retry behavior outside the common J1 policy;
- labelled corpus, offline evaluation, calibration, thresholds, or baseline comparison;
- provider/model/version admission;
- consumer integration or migration;
- shadow or live execution;
- deployment, infrastructure, release, or tag;
- implementation of the accepted-pending `gpu_whisper`, `openai_external`, `deepseek_external`, `STT_SEGMENTS`, or `local_gpu_whisper` D7 extensions.

## Dependencies and Execution Order

1. T001 is the mandatory opening gate.
2. T002–T006 may proceed in parallel after T001 and must fail for the expected missing-contract reason.
3. T007 and T008 satisfy the foundational value/error tests.
4. T009 precedes T011; T010 depends on T007/T008.
5. T012 depends on T008/T011; T013 depends on T010; these may then proceed in parallel.
6. T014 follows T010 and T012.
7. T015 → T016 → T017 → T018 are sequential closing gates.

## J1 Completion Definition

J1 is technically complete only when T001–T017 are checked with exact-head evidence. T018 remains a separate human release decision. Completion of J1 never implies J2 authorization, provider admission, consumer rollout, deployment, release, or tag.
