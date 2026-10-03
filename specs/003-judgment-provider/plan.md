# Implementation Plan: Judgment Provider v0.1

**Status**: `AUTHORIZE_J1_CONTRACT_ONLY`, scope `contract_only`.

The authorization already recorded at platform-control Remote Truth
`717cace0d109105c406723de30cd72e4e3ed7dd4`
(`coordination/initiatives/platform-factory-global-roadmap/evidence/operator-decision-authorize-j1-contract-only.yaml`)
allows the callable provider-neutral contract. It does not allow J2, real
provider network execution, credentials, deployment, or catalog admission.

## Goal

Define and verify a provider-neutral, typed `JudgmentProvider` execution
boundary that produces bounded advisory signals while preserving privacy,
deterministic rules, human gates, and baseline behavior on failure.

## Architecture

J1 will add a small judgment-specific contract boundary rather than reuse text
completion or JSON-mode APIs. A validated request flows through privacy/egress
gating, restricted deterministic mock execution (J1 mock-only execution does not use a production JUDGMENT admission; real provider execution remains blocked until future admission exists), one
deadline-bounded execution loop, response validation, and metadata-only
telemetry. Consumers retain decision packs, thresholds, deterministic rules,
and durable workflow retry.

J1 has no real provider adapter. A test-only `mock_judgment` is sufficient to
exercise the contract and failure semantics. `typesafe_jev` and `kev_local`
remain J2-or-later work.

## Technical context and constraints

- Runtime baseline: ai-core `v0.3.1` at `85c82f5`.
- D7 canon: operator decision D7 (judgment provider canon, platform-control
  ADR-024, merged in platform-control #338); v0.3.1 plus pc#291 extensions,
  all documented as `accepted-in-canon, implementation pending`.
- Current runtime provider identities and capabilities are not modified by this
  documentation package.
- J1 execution is restricted to deterministic mock_judgment only; real provider execution requires future JUDGMENT admission (J2+). Text or structured JSON authorization does not grant judgment authority.
- One total monotonic deadline includes validation, bounded retry, and any
  allowed fallback. Retry/fallback loops must have one owner.
- Privacy/egress denial occurs before transport construction, credential lookup,
  retry, and fallback.
- Hosted Jev permits only `DataClass.SYNTHETIC` and `DataClass.PUBLIC_NO_PII`
  from `src/ai_core/privacy.py`. All other `DataClass` values are local-only or
  denied. ZDR is not assumed. `kev_local` has no hosted fallback.
- Exact provider/model/version pins are mandatory for admitted behavior; no
  `*-latest` selector is valid for such behavior.
- Thresholds are scoped to provider, model, version, and decision pack. They
  are not portable.
- Telemetry is metadata-only by default and excludes prompts, responses,
  payload fragments, and credentials.
- This plan does not authorize provider admission, deployment, consumer
  migration, release, or automatic action.

## Module boundaries

`src/ai_core/judgment_contracts.py` now holds the authorized callable contract:
typed request/response, validation, normalized errors, privacy/egress check,
one deadline, and metadata-only telemetry. Rollback of that file is a revert
of its commit. The rows below that are not that file are still future work.
This authorization does not create them, and it does not create provider
network execution.

| Proposed surface | Single responsibility |
| --- | --- |
| `src/ai_core/judgment_contracts.py` | Batch-first `Binary` / `Choice` / `Score` questions and answers, exact pins, and decision-pack reference. No provider-neutral Noul. |
| `src/ai_core/judgment_validation.py` | Deterministic input and provider-response validation with no transport code. |
| `src/ai_core/judgment_errors.py` | Provider-neutral error categories and conversion to typed judgment errors. |
| `src/ai_core/judgment_runtime.py` | One total-deadline execution loop, bounded retry/fallback ownership, and fail-neutral result handling. |
| `src/ai_core/judgment_privacy.py` | Judgment-specific mapping to existing privacy/egress contracts before any transport attempt. |
| `src/ai_core/judgment_telemetry.py` | Metadata-only event shaping and explicit payload exclusion. |
| `src/ai_core/judgment_mock.py` | Test-only deterministic `mock_judgment` implementation. |
| `tests/test_judgment_*.py` | Contract, validation, privacy, deadline, serialization, telemetry, and J1 fail-closed evidence. |

Catalog integration belongs in the existing catalog/capability/routing surfaces
only after J1 authorization. It must preserve their explicit identity,
capability, privacy/egress, health, and policy gates. Consumer integration is
handled later as a fail-neutral protocol for consumers and is not part of J1.

## Implementation sequence

1. **J1 contract** — add typed contracts and provider-neutral errors; define
   serialization only for typed values, not provider text.
2. **J1 tests** — write contract, validation, privacy, deadline, telemetry,
   serialization, and J1 fail-closed tests with the deterministic mock (no
   consumer state fixtures).
3. **J1 review** — verify exact implementation head against this specification,
   D7 compatibility, source/runtime diffs, and test evidence.
4. **Release decision** — a human/operator governance decision determines
   whether a reviewed J1 artifact may be admitted. No automatic transition,
   provider admission, or release follows from test success.

## Test strategy

| Test group | Deterministic evidence |
| --- | --- |
| Contract tests | Valid Binary, Choice, and Score answer round trips; undeclared choices, non-finite or out-of-range scores, mismatched variants, missing exact pins, and invalid decision-pack references fail before consumers observe a result. |
| Privacy gate tests | Hosted providers receive only eligible classification; gate denial happens before mock transport, credential resolver, retry scheduler, and fallback selector are invoked. |
| Deadline tests | Timeout, 429, 529, and provider-unavailable paths consume one shared deadline; no retry or fallback begins after budget exhaustion. |
| Fallback tests | `kev_local` never selects a hosted fallback; unavailable paths yield typed errors or policy-permitted fallback only (no consumer baseline assertions). |
| Serialization tests | Typed request and response metadata serialize deterministically; no free-form provider response is accepted as a result. |
| Telemetry tests | Allowed metadata is emitted; prompts, responses, payload fragments, decision values, and credentials are absent by default. |
| Fail-closed contract tests | Invalid input/output, privacy denial, deadline exhaustion, and mock error fixtures never expose unvalidated results or auto-approve; consumer model/effort/context, `needs_review`, and low-confidence routing are out of scope (see `spec.md` **Deferred beyond J1**). |
| Catalog tests | A future `JUDGMENT` request remains ineligible without identity, exact model/capability authorization, privacy/egress, health, and governance admission. |

## Migration and compatibility constraints

- Maintain the factual v0.3.1 runtime inventory: four provider identities,
  four capabilities, and five existing aliases.
- Treat pc#291 provider identities, `STT_SEGMENTS`, and migration aliases as
  D7 canon with `accepted-in-canon, implementation pending` status until a
  separately authorized implementation updates runtime surfaces.
- Keep generic `ollama` ambiguous and fail-closed.
- Do not change v0.3.1 aliases, default candidates, provider identities, or
  existing text/structured-JSON behavior as an incidental J1 migration.
- Do not claim an adapter, provider, model, or decision pack is admitted merely
  because its contract type or test double exists.
- Consumers retain ownership of decision packs, evaluation data, thresholds,
  deterministic decisions, human review, and durable retry.

## Risk register

| Risk | Control | Stop condition |
| --- | --- | --- |
| Text/JSON behavior is mistaken for judgment | Separate typed interface and response validation; contract tests reject free-form results. | Any design reuses a text provider as the judgment interface. |
| Payload reaches hosted transport or telemetry before a policy gate | Gate before transport/credential/retry/fallback; payload-exclusion tests. | The required ordering cannot be proved. |
| Retry or fallback exceeds budget | One monotonic deadline and one loop owner; fake-clock tests. | More than one deadline or retry owner is required. |
| Local-sensitive path silently reaches hosted provider | Explicit no-hosted-fallback rule for `kev_local`; routing tests. | A local provider requires a hosted fallback. |
| Threshold is copied across model/provider/pack | Make threshold scope part of the typed result metadata and test fixtures. | A consumer requests global threshold reuse. |
| D7 pending extensions are represented as runtime facts | Compatibility tables distinguish current runtime from accepted canon. | J1 requires undocumented runtime expansion or D7 facts conflict with v0.3.1 baseline. |
| Provider response gains authority | J1 fail-closed contract tests and explicit authority prohibitions. | A provider result is proposed to authorize protected action. |

## Exact human gates

1. D7 canon remains recorded as v0.3.1 plus pc#291 extensions; no unresolved
   architecture decision may be inferred by the implementer.
2. `AUTHORIZE_J1_CONTRACT_ONLY` with scope `contract_only` is already recorded
   at platform-control `717cace0d109105c406723de30cd72e4e3ed7dd4`. Callable
   contract runtime is authorized. Provider network execution is not.
3. Before any catalog or runtime change, the implementation must receive
   platform-control review because it changes provider/capability contracts.
4. Before J1 is accepted, a human reviews the exact head, contract tests,
   privacy ordering, deadline evidence, telemetry evidence, and runtime diff.
5. Provider adapters, credentials, network calls, offline evaluation,
   deployment, consumer migration, and provider admission require separate
   later approvals.
6. A release or admission decision remains human-controlled even if all J1
   tests pass.

## Rollback

Rollback of the callable contract is a revert of `src/ai_core/judgment_contracts.py`
and its tests. No provider credential, deployment, consumer state, or network
execution is introduced. J2 and catalog admission stay unauthorized.
