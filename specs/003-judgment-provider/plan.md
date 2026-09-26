# Implementation Plan: Provider-Neutral Judgment Contract

**Branch**: `cursor/d7-judgment-provider-spec-23ec` | **Spec**: `specs/003-judgment-provider/spec.md`

**Package Type**: Docs-only design for a future, separately authorized J1 implementation

## Summary

Define a future provider-neutral `JudgmentProvider` boundary with typed `Choice`, `Score`, and `Noul` results; strict request/response validation; privacy and egress checks before transport; one total deadline; bounded retry and deterministic fallback; normalized errors; exact model/version pinning; metadata-only telemetry; and no authority over protected actions.

The future implementation will integrate with provider eligibility through a dedicated `JUDGMENT` capability. This package creates no runtime module, enum member, catalog entry, adapter, credential, transport, dependency, deployment, release, or tag.

## Technical Context

**Language/Version**: Future J1 must preserve the repository's supported Python baseline (`>=3.10`); this docs-only package adds no Python.

**Primary Dependencies**: Future J1 should use the standard library and existing ai-core contracts. No provider SDK or new dependency is authorized in J1.

**Storage**: None in J1. Decision packs remain consumer-owned and versioned outside ai-core.

**Testing**: Future pytest contract, privacy-gate, deadline/retry, fallback, serialization, telemetry, and authority tests using deterministic fakes only.

**Target Platform**: ai-core library consumers; no deployment target in this package.

**Project Type**: Shared provider-neutral library contract.

**Performance Goals**: No performance admission in J1. The contract requires one enforceable total deadline and deterministic bounded attempts.

**Constraints**:

- docs-only now; runtime work requires a separate operator authorization;
- `JudgmentProvider` is not TextProvider/chat/JSON mode;
- one total deadline; `max_same_provider_retries` is `0` or `1`;
- no hosted fallback for local/no-egress;
- privacy and egress checks precede transport;
- hosted Jev receives only `PUBLIC` or contractually confirmed `ANONYMIZED` payloads;
- ZDR is not assumed;
- exact model and version pinning; `*-latest` is invalid for admitted behavior;
- metadata-only telemetry by default;
- thresholds are not portable across provider/model/version/decision-pack tuples;
- no automatic or protected action authority.

**Scale/Scope**: One provider-neutral contract, three output variants, one deterministic mock, and policy tests. Real provider adapters and evaluation are J2 or later.

## Constitution and Governance Check

`.specify/memory/constitution.md` is an unratified placeholder. Operative gates come from `AGENTS.md`, platform-control governance, the operator's D7 decision, ADR-023, and the semantic judgment pilot plan.

Pre-design gates:

- PASS — D7 canon is fixed as ai-core `v0.3.1` plus the accepted platform-control `#291` extensions.
- PASS — runtime `v0.3.1` facts and accepted-but-pending extensions are explicitly separated.
- PASS — the package changes only the three Spec Kit files and one transition-plan status link.
- PASS — no shared runtime contract, provider behavior, tracing, dependency, deployment, or release state changes.
- PASS — `JudgmentProvider`, `JUDGMENT`, and all implementations remain proposed.
- PASS — privacy, authority, and failure semantics are fail-closed or fail-neutral as specified.
- PASS — no unresolved architecture decision is introduced.

Post-design re-check: the proposed J1 boundaries stay inside ai-core ownership; provider admission, decision packs, thresholds, consumers, and deployment remain outside J1.

## J1 Delivery Sequence

No stage advances automatically.

### 0. Opening Human Gate

Before any J1 runtime edit:

1. An operator records `AUTHORIZE_J1`.
2. Platform-control reviews the exact D7 canon and confirms that `JUDGMENT` implementation may begin.
3. The J1 branch starts from an explicitly recorded ai-core base SHA.
4. Scope remains contract + deterministic mock only; real provider calls remain unauthorized.

If any item is absent or contradictory, J1 stops before code changes.

### 1. Contract Tests First

Write failing tests for:

- typed request construction and each result variant;
- invalid requests and provider responses;
- serialization round trips and unknown-field rejection;
- future `JUDGMENT` catalog eligibility;
- privacy/egress denial before transport;
- exact model/version pinning;
- one total deadline and bounded retry;
- local/no-egress hosted-fallback prohibition;
- normalized errors and the fail-neutral/fail-closed matrix;
- metadata-only telemetry;
- authority limits.

The tests must fail because J1 symbols are absent, not because fixtures use real credentials or network access.

### 2. Minimal Contract Implementation

Implement only enough to satisfy the tests:

1. immutable request/result value types;
2. provider-neutral error values;
3. request and response validation;
4. the separate `JudgmentProvider` interface;
5. policy orchestration for eligibility, privacy, deadline, retry, and fallback;
6. deterministic `mock_judgment`;
7. metadata-only telemetry records.

No adapter, SDK, endpoint, credential, consumer, or deployment code enters J1.

### 3. Review and Evidence

Run focused and full regression checks. Produce exact-head evidence for:

- all J1 acceptance criteria;
- zero transport calls on privacy/egress denial;
- zero payload fields in default telemetry;
- zero hosted fallback calls in local/no-egress cases;
- unchanged existing provider identity, alias, capability, routing, and tracing behavior except for the separately authorized J1 surfaces;
- no dependency changes.

Platform-control and the operator review the exact head. Findings return to tests and implementation; they do not trigger automatic scope expansion.

### 4. Separate Release Decision

Passing J1 tests and review makes the contract eligible for a separate release decision only. It does not admit any provider, authorize J2, create a release, or create a tag.

## Proposed Module Boundaries

These are future J1 surfaces; this package does not create them.

```text
src/ai_core/
├── judgment_models.py       # immutable request, Choice, Score, Noul, result metadata
├── judgment_errors.py       # provider-neutral normalized error values
├── judgment_provider.py     # separate interface and one-invocation contract
├── judgment_policy.py       # eligibility, privacy, deadline, retry, fallback decisions
└── mock_judgment.py         # deterministic test-only implementation

tests/
├── test_judgment_contract.py
├── test_judgment_privacy.py
├── test_judgment_deadline.py
├── test_judgment_serialization.py
├── test_judgment_telemetry.py
└── test_judgment_authority.py
```

### Boundary Responsibilities

| Surface | Owns | Must not own |
| --- | --- | --- |
| `judgment_models.py` | Typed immutable values and local validation rules. | Transport, routing, thresholds, provider SDKs. |
| `judgment_errors.py` | Stable normalized error vocabulary and retry/fallback flags. | Raw provider payloads or credentials. |
| `judgment_provider.py` | Separate provider-neutral invocation interface. | Text/chat abstraction, admission, consumer policy. |
| `judgment_policy.py` | Pre-transport gates, one deadline, bounded attempts, deterministic fallback. | Nested fallback, domain thresholds, durable workflow retry. |
| `mock_judgment.py` | Deterministic contract behavior for tests. | Production admission or network access. |
| Consumers | Decision packs, thresholds, deterministic rules, human review, durable workflow retry. | Provider transport or ai-core admission. |
| Platform-control | Governance, admission, privacy policy, protected gates, evidence. | Consumer domain thresholds. |

The implementation should keep functions and value types small and explicit. It should avoid inheritance-based provider hierarchies, reflection, dynamic registration, and assignment of external functions onto classes.

## Request Flow

```text
consumer-owned versioned decision pack
                    ↓
typed JudgmentRequest validation
                    ↓
provider identity + JUDGMENT + admission + exact-version gates
                    ↓
privacy/egress gate before transport
                    ↓
one shared monotonic deadline
                    ↓
provider attempt → response validation
        ↓ retry at most once only for RATE_LIMIT/TIMEOUT
        ↓ fallback only to independently eligible candidate
                    ↓
validated Choice | Score | Noul
                    ↓
consumer threshold + deterministic rules + human gates
```

At every failure point, the specification's fail-neutral/fail-closed matrix applies. The provider result never directly executes an action.

## Test Strategy

### Contract Tests

- Construct each valid request/output variant.
- Reject empty identifiers, duplicate choice keys, invalid score bounds, unknown output kind, and invalid retry count.
- Reject multiple output variants, wrong result kind, undeclared keys/reasons, non-finite or out-of-range scores, booleans as scores, invalid confidence, metadata mismatch, and unknown response fields.
- Prove `JudgmentProvider` cannot be substituted by a text/chat provider contract.

### Privacy Gate Tests

- Assert transport-call count is zero for `SECRET`, denied egress, absent contractual anonymization evidence, and ineligible hosted payloads.
- Assert sanitization/surrogation does not manufacture anonymized classification.
- Assert ZDR is false/unknown without contractual evidence.
- Assert every fallback candidate repeats the complete pre-transport gate.
- Assert local/no-egress policy produces zero hosted fallback calls.

### Deadline, Retry, and Fallback Tests

- Use a fake monotonic clock.
- Prove all attempts share one deadline.
- Prove retry count accepts only `0` or `1`.
- Prove only `RATE_LIMIT` and `TIMEOUT` can use the optional same-provider retry.
- Prove no attempt begins without a safe remaining budget.
- Prove fallback order is deterministic and no nested fallback occurs.
- Prove terminal, privacy, authority, and unknown errors stop safely.

### Serialization Tests

- Round-trip every valid request and result through the J1 serialization boundary.
- Reject unknown fields, missing required fields, wrong primitive types, non-finite values, and version mismatch.
- Preserve exact IDs and versions without case folding, whitespace trimming, wildcard expansion, or alias guessing.

### Telemetry Tests

- Allow only the metadata fields listed in the specification.
- Assert prompt/input, raw request/response, selected choice, score, Noul reason, explanation, credentials, and protected instructions are absent by default.
- Prove telemetry failure is non-authoritative and cannot change the judgment result or failure mode.

### Authority and Failure Tests

For every row in the fail-neutral/fail-closed matrix, test provider error, timeout, invalid response, missing confidence, and below-threshold confidence. Assert the deterministic baseline or human gate remains authoritative.

### Regression Tests

- Existing provider catalog and alias sets remain exact unless a separately authorized D7 implementation package changes them.
- Runtime `v0.3.1` capabilities remain distinct from accepted-in-canon pending extensions.
- Existing privacy, routing, deadline, transport, tracing, and root API tests remain green.

## Migration and Compatibility Constraints

1. D7 canon is ai-core `v0.3.1@85c82f5` plus accepted-in-canon pending provider identities `gpu_whisper`, `openai_external`, `deepseek_external`, capability `STT_SEGMENTS`, and the `local_gpu_whisper` migration alias.
2. J1 does not depend on those pending extensions and must not claim they exist in runtime until separately implemented.
3. The future `JUDGMENT` capability is independent from `TEXT` and `STRUCTURED_JSON`; no automatic capability promotion is allowed.
4. Existing provider aliases remain identity normalization only and grant no model, capability, admission, privacy, or runtime authority.
5. Generic `ollama` remains ambiguous and fail-closed.
6. Consumer decision packs remain versioned independently from ai-core and provider model versions.
7. Thresholds cannot migrate across provider/model/version/decision-pack tuples without new evaluation and evidence.
8. Existing consumers continue baseline behavior until separately migrated.
9. No root API export is assumed; any public export requires explicit review in J1.
10. Real adapters, SDK floors, credentials, and network formats belong to J2 or later.

## Risk Register

| Risk | Consequence | Required mitigation / evidence |
| --- | --- | --- |
| Judgment is implemented as text or JSON generation | Provider-specific parsing leaks to consumers; invalid output may reach decisions. | Separate interface and typed contract tests; no text/chat substitution. |
| Catalog identity is mistaken for admission | Unreviewed provider becomes executable. | Independent identity, capability, exact-version, admission, privacy, and egress gates. |
| Accepted D7 extensions are reported as runtime | False availability and unsafe consumer assumptions. | Separate runtime and accepted-pending tables; regression scan for availability claims. |
| Hosted Jev receives private/raw data | Privacy breach. | Pre-transport gate; only PUBLIC or contractually confirmed ANONYMIZED; zero-call denial tests. |
| ZDR is assumed | Unsupported retention claim. | Require contractual evidence in admission record; default unknown/false. |
| Retry/fallback exceeds deadline | Latency cascade and hidden provider amplification. | One monotonic deadline, retry range `0..1`, fake-clock tests. |
| Local provider falls back to hosted | No-egress violation. | Explicit prohibition and zero hosted-call tests. |
| Thresholds are copied | Silent quality or safety drift. | Key calibration to exact provider/model/version/pack tuple. |
| Telemetry captures semantic payload | Sensitive data or decision leakage. | Metadata allowlist and negative payload-field tests. |
| Confidence gains authority | Auto-approval or protected action. | Consumer-owned thresholds plus authority matrix and human gates. |
| Mock is treated as production provider | False operational readiness. | Test-only location, no admission, and explicit status metadata. |
| J1 expands into adapters or deployment | Governance boundary violation. | STOP conditions and exact changed-surface review. |

## Exact Human Gates

| Gate | Required human decision | Evidence required | If absent |
| --- | --- | --- | --- |
| J1 opening | Operator records `AUTHORIZE_J1`; platform-control confirms D7/JUDGMENT scope. | Decision reference and exact ai-core base SHA. | Stop before runtime edits. |
| Contract review | Operator/platform reviewer accepts typed fields, validation, errors, privacy, deadline, retry, fallback, telemetry, and authority limits. | Exact-head diff and contract test results. | Return to J1 tests/design. |
| Security/privacy review | Reviewer confirms hosted data gate, no hosted fallback for local policy, ZDR evidence rule, and metadata-only telemetry. | Negative transport-call and telemetry tests. | J1 cannot close. |
| J1 closing | Operator accepts exact-head J1 implementation. | Full local checks, changed-file inventory, risks, rollback. | No release decision. |
| Release decision | Separately authorized release/tag decision. | Accepted J1 head and release evidence. | Contract remains unreleased. |
| J2 opening | Separate authorization for adapters/evaluation. | Provider-specific plan, data policy, credentials boundary, evaluation design. | No real adapter or network work. |
| Provider admission | Per-provider/model/version/decision-pack governance acceptance. | Evaluation, calibration, privacy, reliability, and operational evidence. | Provider remains ineligible. |
| Consumer rollout | Per-consumer and per-decision-pack approval. | Shadow evidence and preserved deterministic gates. | No consumer behavior change. |

## Rollback

For this docs-only package, rollback is a reviewed revert of:

- `specs/003-judgment-provider/spec.md`
- `specs/003-judgment-provider/plan.md`
- `specs/003-judgment-provider/tasks.md`
- the single judgment-provider status link in `docs/coordination/TRANSITION_PLAN.md`

There is no runtime, dependency, data, deployment, release, or provider state to roll back.

## Complexity Tracking

No constitution violation or complexity exception is required. The separate typed interface is a fixed D7 decision and prevents provider-specific concerns from entering existing text-generation contracts.
