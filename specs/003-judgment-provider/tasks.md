# Tasks: Judgment Provider v0.1

**Authority**: `spec.md` and `plan.md`.

**Package type**: J1 `contract_only` implementation checklist (ADR-023,
`AUTHORIZE_J1_CONTRACT_ONLY`). Catalog promotion and real adapters remain J2+.

## J1 prerequisites

- [ ] **J001 — Confirm the bounded implementation gate**
  - **Inputs**: `AUTHORIZE_J1` with scope `contract_only`, current state
    `HOLD_J1`, approved D7 compatibility statement, exact v0.3.1 baseline,
    and platform-control review requirement.
  - **Changed surfaces**: none until the gate is confirmed.
  - **Deterministic acceptance**: the written authorization names J1 and the
    `contract_only` scope; the baseline remains v0.3.1 plus pc#291 extensions
    marked `accepted-in-canon, implementation pending`; no pending
    architecture decision is left to the implementer.
  - **STOP**: authorization is absent, D7 facts conflict with the baseline, or
    a new provider/authority decision is needed.

## J1 contract and validation

- [x] **J002 — Define immutable typed judgment values**
  - **Inputs**: `JudgmentRequest`, `JudgmentResponse`, `Binary`/`Choice`/`Score`
    question/answer variants, decision-pack reference, exact provider/model/version
    pin, and total deadline requirements from `spec.md`.
  - **Changed surfaces**: future `judgment_contracts` module and focused unit
    tests.
  - **Deterministic acceptance**: batch answers map 1:1 to questions; variants
    match; binary probability stays in `[0,1]` without bool coercion; exact pins
    reject `*-latest`.
  - **STOP**: the proposed API becomes a text-completion, JSON-mode, or
    untyped-dictionary interface.

- [x] **J003 — Validate requests before execution**
  - **Inputs**: typed values from J002 and consumer-owned decision-pack
    metadata.
  - **Changed surfaces**: future `judgment_validation` module and invalid-input
    contract tests.
  - **Deterministic acceptance**: empty IDs, duplicate choices, unknown
    decision-pack versions, invalid classifications, undeclared score scales,
    expired deadlines, and incomplete exact pins fail with `invalid_request`;
    no mock transport call occurs.
  - **STOP**: validation needs a consumer threshold, data set, or business
    decision outside the typed contract.

- [x] **J004 — Validate provider responses before consumer visibility**
  - **Inputs**: typed request, proposed response variant, and
    provider-neutral error taxonomy.
  - **Changed surfaces**: future `judgment_validation` and
    `judgment_errors` modules plus response-validation tests.
  - **Deterministic acceptance**: undeclared choices, out-of-range/non-finite
    scores, ambiguous variants, missing pins, and malformed provider output
    become `invalid_provider_response`; consumer callbacks receive no result.
  - **STOP**: response acceptance requires parsing or trusting free-form
    provider text.

## J1 policy and execution boundary

- [ ] **J005 — Add the future `JUDGMENT` catalog gate**
  - **Inputs**: existing provider identity, capability, routing, privacy,
    egress, health, and policy contracts.
  - **Changed surfaces**: future capability/catalog/routing changes and
    catalog eligibility tests.
  - **Deterministic acceptance**: a judgment candidate is ineligible unless it
    has a known identity, exact model/capability authorization,
    privacy/egress eligibility, acceptable health, and governance admission;
    text and structured-JSON authorizations do not satisfy `JUDGMENT`.
  - **STOP**: the change would alter existing v0.3.1 provider identities,
    aliases, or behavior without separate approval.

- [x] **J006 — Enforce privacy and egress before transport**
  - **Inputs**: request classification, provider boundary, egress
    authorization, hosted-Jev and local-provider constraints.
  - **Changed surfaces**: future judgment privacy gate and ordering tests with
    fake transport, credential resolver, retry scheduler, and fallback
    selector.
  - **Deterministic acceptance**: denied requests return
    `privacy_egress_denied`; all fakes show zero calls; hosted Jev receives
    only `DataClass.SYNTHETIC` and `DataClass.PUBLIC_NO_PII`; `kev_local` has
    no hosted fallback.
  - **STOP**: zero-data-retention is assumed without evidence, a sensitive
    local flow requires hosted fallback, or ordering cannot be tested.

- [x] **J007 — Implement one bounded execution loop**
  - **Inputs**: normalized errors, a monotonic total deadline, and
    policy-permitted candidate order.
  - **Changed surfaces**: future `judgment_runtime` module and fake-clock
    deadline/retry/fallback tests.
  - **Deterministic acceptance**: one owner governs retries and fallback;
    timeout, 429, 529, and unavailable cases consume the same deadline; no
    attempt starts after budget exhaustion; authentication and invalid-request
    errors do not retry.
  - **STOP**: an adapter, transport, or consumer introduces a nested retry or
    separate deadline.

- [x] **J008 — Add only the deterministic test mock**
  - **Inputs**: validated contract and the one-loop execution boundary.
  - **Changed surfaces**: future `mock_judgment` module and contract/failure
    tests.
  - **Deterministic acceptance**: the mock produces declared binary, choice,
    score, timeout, rate-limit, unavailable, and invalid-response fixtures
    without credentials or network access; it cannot be selected as a
    production provider.
  - **STOP**: the task requires an SDK, external endpoint, credential, or
    provider admission.

## J1 evidence and review

- [x] **J009 — Prove serialization and telemetry exclusions**
  - **Inputs**: typed contract metadata and telemetry allowlist.
  - **Changed surfaces**: future serialization/telemetry helpers and focused
    tests.
  - **Deterministic acceptance**: serialized typed values round-trip; emitted
    telemetry contains only outcome, normalized error category, latency, retry
    count, identity, exact model/version, and decision-pack ID/version; tests
    prove prompts, responses, payload fragments, decision values, and
    credentials are absent by default.
  - **STOP**: observability requires prompt/response or payload capture by
    default.

- [ ] **J010 — Verify J1 fail-closed contract outcomes (ai-core only)**
  - **Inputs**: J1 ai-core contract boundary in `spec.md`, provider-neutral
    error taxonomy, privacy ordering from J006, deadline behavior from J007,
    and J004–J008 test doubles including `mock_judgment`.
  - **Changed surfaces**: future judgment contract/runtime tests only (no
    consumer integration harness).
  - **Deterministic acceptance**: invalid requests fail with `invalid_request`
    before transport; denied privacy/egress fails closed before transport;
    timeout, rate-limit, unavailable, and malformed mock responses surface
    only normalized typed errors or validated `noul`/choice variants; consumer
    callbacks never receive unvalidated provider output; telemetry stays
    metadata-only. Tests do **not** assert consumer model/effort/context,
    `needs_review`, low-confidence routing, tool calls, or queue state.
  - **STOP**: any test outcome auto-approves, authorizes, merges, grants
    access, replaces a deterministic check, or requires consumer state
    fixtures.

- [ ] **J011 — Conduct exact-head review and human release decision**
  - **Inputs**: complete J1 diff, all J1 test results, D7 compatibility check,
    platform-control review, and operator decision.
  - **Changed surfaces**: review evidence and release/admission record only;
    no automatic runtime transition.
  - **Deterministic acceptance**: reviewers verify no unintended
    provider/alias/runtime drift, all J1 acceptance criteria pass, and the
    result remains unadmitted until an explicit human decision records
    otherwise.
  - **STOP**: tests are missing, the exact head differs from reviewed evidence,
    or admission/release is assumed from CI or test success.

## Explicitly excluded from J1

The following are J2-or-later work and are not implementation tasks for J1:

- `typesafe_jev` and `kev_local` adapters, their SDKs, credentials, endpoints,
  network integrations, or real calls;
- offline evaluation, labelled corpora, calibration, threshold selection, and
  provider/model/version/decision-pack admission;
- consumer integrations, the later fail-neutral consumer state protocol,
  shadow runs, durable workflow retry, deployment, release, or production
  routing;
- additions of pc#291 provider identities, aliases, or `STT_SEGMENTS` to
  runtime code unless separately authorized.

## Deferred beyond J1 (C7 / architect response #6)

Per AI-JUDGMENT-J010-BOUNDARY-01, these are not J1 tasks or J010 acceptance
checks; they move to a post-J1 increment with explicit authorization:

- baseline preservation for **model, effort, and context** on judgment failure;
- consumer **`needs_review`** routing state for on-prem documents;
- **low-confidence** routing and baseline handling outside typed ai-core errors.
