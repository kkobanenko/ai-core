# Implementation Plan: Judgment Provider v0.1

**Status**: PLAN_ONLY. This plan describes a future separately authorized J1
implementation. This documentation package creates no runtime behavior.

## Goal

Define and verify a provider-neutral, typed `JudgmentProvider` execution
boundary that produces bounded advisory signals while preserving privacy,
deterministic rules, human gates, and baseline behavior on failure.

## Architecture

J1 will add a small judgment-specific contract boundary rather than reuse text
completion or JSON-mode APIs. A validated request flows through privacy/egress
gating, catalog eligibility for the future `JUDGMENT` capability, one
deadline-bounded execution loop, response validation, and metadata-only
telemetry. Consumers retain decision packs, thresholds, deterministic rules,
and durable workflow retry.

J1 has no real provider adapter. A test-only `mock_judgment` is sufficient to
exercise the contract and failure semantics. `typesafe_jev` and `kev_local`
remain J2-or-later work.

## Technical context and constraints

- Runtime baseline: ai-core `v0.3.1` at `85c82f5`.
- D7 canon: v0.3.1 plus pc#291 extensions, all documented as
  `accepted-in-canon, implementation pending`.
- Current runtime provider identities and capabilities are not modified by this
  documentation package.
- A future J1 implementation must add `JUDGMENT` as a distinct capability; it
  must not make text or structured JSON authorization equivalent to judgment.
- One total monotonic deadline includes validation, bounded retry, and any
  allowed fallback. Retry/fallback loops must have one owner.
- Privacy/egress denial occurs before transport construction, credential lookup,
  retry, and fallback.
- Hosted Jev permits only `PUBLIC` or confirmed `ANONYMIZED` data. ZDR is not
  assumed. `kev_local` has no hosted fallback.
- Exact provider/model/version pins are mandatory for admitted behavior; no
  `*-latest` selector is valid for such behavior.
- Thresholds are scoped to provider, model, version, and decision pack. They
  are not portable.
- Telemetry is metadata-only by default and excludes prompts, responses,
  payload fragments, and credentials.
- This plan does not authorize provider admission, deployment, consumer
  migration, release, or automatic action.

## Proposed module boundaries

The following boundaries are proposed for a future J1 implementation. They do
not create files in this package.

| Proposed surface | Single responsibility |
| --- | --- |
| `src/ai_core/judgment_contracts.py` | Immutable request/response, `Choice`, `Score`, `Noul`, exact-pin, and decision-pack reference types. |
| `src/ai_core/judgment_validation.py` | Deterministic input and provider-response validation with no transport code. |
| `src/ai_core/judgment_errors.py` | Provider-neutral error categories and conversion to typed judgment errors. |
| `src/ai_core/judgment_runtime.py` | One total-deadline execution loop, bounded retry/fallback ownership, and fail-neutral result handling. |
| `src/ai_core/judgment_privacy.py` | Judgment-specific mapping to existing privacy/egress contracts before any transport attempt. |
| `src/ai_core/judgment_telemetry.py` | Metadata-only event shaping and explicit payload exclusion. |
| `src/ai_core/judgment_mock.py` | Test-only deterministic `mock_judgment` implementation. |
| `tests/test_judgment_*.py` | Contract, validation, privacy, deadline, serialization, telemetry, and failure-matrix evidence. |

Catalog integration belongs in the existing catalog/capability/routing surfaces
only after J1 authorization. It must preserve their explicit identity,
capability, privacy/egress, health, and policy gates.

## Implementation sequence

1. **J1 contract** — add typed contracts and provider-neutral errors; define
   serialization only for typed values, not provider text.
2. **J1 tests** — write contract, validation, privacy, deadline, telemetry,
   serialization, and failure-matrix tests with the deterministic mock.
3. **J1 review** — verify exact implementation head against this specification,
   D7 compatibility, source/runtime diffs, and test evidence.
4. **Release decision** — a human/operator governance decision determines
   whether a reviewed J1 artifact may be admitted. No automatic transition,
   provider admission, or release follows from test success.

## Test strategy

| Test group | Deterministic evidence |
| --- | --- |
| Contract tests | Valid `Choice`, `Score`, and `Noul` round trips; undeclared choices, non-finite/out-of-range scores, ambiguous variants, missing exact pins, and invalid decision-pack references fail before consumers observe a result. |
| Privacy gate tests | Hosted providers receive only eligible classification; gate denial happens before mock transport, credential resolver, retry scheduler, and fallback selector are invoked. |
| Deadline tests | Timeout, 429, 529, and provider-unavailable paths consume one shared deadline; no retry or fallback begins after budget exhaustion. |
| Fallback tests | `kev_local` never selects a hosted fallback; unavailable/low-confidence outcomes preserve the declared baseline. |
| Serialization tests | Typed request and response metadata serialize deterministically; no free-form provider response is accepted as a result. |
| Telemetry tests | Allowed metadata is emitted; prompts, responses, payload fragments, decision values, and credentials are absent by default. |
| Failure-matrix tests | Each specified decision surface produces its fail-neutral or fail-closed outcome, never an automatic approval. |
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
| Provider response gains authority | Fail-neutral/fail-closed matrix and explicit authority prohibitions. | A provider result is proposed to authorize protected action. |

## Exact human gates

1. D7 canon remains recorded as v0.3.1 plus pc#291 extensions; no unresolved
   architecture decision may be inferred by the implementer.
2. Before J1 starts, `AUTHORIZE_J1` must be explicitly recorded by the
   authorized operator/governance process.
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

This package is documentation only: rollback is a revert of its documentation
commit. A future J1 implementation must make its own rollback plan before it
changes any runtime surface. No provider, credential, deployment, or consumer
state is introduced here.
