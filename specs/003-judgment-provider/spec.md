# Feature Specification: Provider-Neutral Judgment Contract

**Feature Branch**: `cursor/d7-judgment-provider-spec-23ec`

**Status**: Proposed / plan-only / docs-only

**Authorization**: `AUTHORIZE_DOCS_AND_GOVERNANCE_ONLY`; no runtime authorization

**Input**: D7 operator decision, ADR-023, the semantic judgment pilot plan, ai-core `v0.3.1`, and the accepted platform-control provider extensions.

## Problem Statement

Coordinated products need a fast, typed judgment signal for bounded advisory decisions without coupling consumers to Jev, a text-generation interface, or provider-specific JSON conventions. The contract must preserve deterministic business rules, protected human gates, privacy policy, and baseline behavior when a provider is unavailable or uncertain.

This specification defines the future J1 contract for a provider-neutral `JudgmentProvider`. It resolves D7 at the design level only. It does not make semantic judgment available in the current runtime.

## Non-Goals

- Implementing `JudgmentProvider`, `JUDGMENT`, transports, adapters, credentials, or network calls.
- Treating judgment as `TextProvider`, chat completion, prompt-to-JSON, or a mode of `STRUCTURED_JSON`.
- Admitting or releasing `typesafe_jev`, `kev_local`, or `mock_judgment`.
- Evaluating provider quality, calibrating thresholds, or building labelled datasets.
- Migrating consumers, decision packs, workflows, deployments, or provider configuration.
- Granting model output authority over deterministic checks, protected actions, legal decisions, or business acceptance.
- Changing the ai-core `v0.3.1` provider catalog, aliases, capability enum, routing, tracing, dependencies, or public API in this docs-only package.

## User Scenarios & Testing

### User Story 1 - Request a typed bounded judgment (Priority: P1)

As a consumer owner, I need one provider-neutral request and response contract so that I can ask for a `Choice`, `Score`, or `Noul` result without depending on provider-specific payloads.

**Why this priority**: Typed validation is the minimum useful J1 boundary and prevents free-form model output from reaching decision logic.

**Independent Test**: Use a future deterministic mock provider to submit one valid request for each output kind and verify that the result is typed, version-bound, and validated before consumer logic receives it.

**Acceptance Scenarios**:

1. **Given** a request declares a finite choice set, **When** the provider returns a declared choice key, **Then** the contract yields a valid `Choice`.
2. **Given** a request declares a finite score range, **When** the provider returns a finite value in that range, **Then** the contract yields a valid `Score`.
3. **Given** a decision pack permits a non-decision reason, **When** the provider abstains with that reason, **Then** the contract yields a valid `Noul` rather than a language-level null.
4. **Given** a response has the wrong output kind, an undeclared key, a non-finite score, or mismatched version metadata, **When** validation runs, **Then** no result reaches consumer decision logic and a normalized validation error is returned.

---

### User Story 2 - Preserve privacy and authority boundaries (Priority: P1)

As the operator, I need every judgment attempt to pass privacy, egress, and authority checks before transport so that advisory output cannot create new access or action authority.

**Why this priority**: A typed result is unsafe if it can leak protected data or bypass deterministic gates.

**Independent Test**: Exercise the privacy and authority matrix with a fake transport and verify that denied requests emit zero transport calls and every provider failure preserves the required baseline behavior.

**Acceptance Scenarios**:

1. **Given** a hosted provider and payload that is neither `PUBLIC` nor contractually confirmed `ANONYMIZED`, **When** eligibility is evaluated, **Then** transport is not called.
2. **Given** a local/no-egress request, **When** the local provider fails, **Then** no hosted fallback is attempted.
3. **Given** any judgment that recommends a protected action, **When** consumer code evaluates it, **Then** deterministic policy and human gates remain authoritative.
4. **Given** an error, timeout, malformed response, or low-confidence result, **When** failure semantics are applied, **Then** the baseline or fail-closed state from this specification is preserved.

---

### User Story 3 - Evolve providers without changing decision ownership (Priority: P2)

As an ai-core maintainer, I need judgment routing to use a future `JUDGMENT` catalog capability while consumers retain their decision packs and thresholds.

**Why this priority**: Provider replacement must not silently move domain policy into ai-core or copy thresholds across providers and versions.

**Independent Test**: Configure future mock catalog entries with and without `JUDGMENT` eligibility and verify that only an explicitly eligible, admitted, exactly pinned provider/model/version can be selected.

**Acceptance Scenarios**:

1. **Given** provider evidence without `JUDGMENT` admission, **When** routing is planned, **Then** the provider is ineligible.
2. **Given** an admitted provider with an unpinned or `*-latest` model, **When** request validation runs, **Then** execution fails before transport.
3. **Given** thresholds calibrated for one provider/model/version/decision-pack tuple, **When** another tuple is selected, **Then** those thresholds are not reused.

### Edge Cases

- An empty choice set, duplicate choice key, inverted score range, empty identifier, or unknown output kind is an invalid request.
- Boolean values are not accepted as numeric scores.
- `NaN`, positive infinity, and negative infinity are invalid scores.
- A response for a different decision pack, question, provider, model, or exact version is invalid.
- Missing confidence never implies approval, downgrade, or fallback authorization.
- Exhausted deadline prevents every remaining retry and fallback.
- A candidate newly accepted into canon but absent from runtime remains ineligible until separately implemented and admitted.
- Generic `ollama` remains ambiguous and fails closed.

## Glossary

| Term | Canonical meaning |
| --- | --- |
| `JudgmentProvider` | A separate typed interface that evaluates one bounded judgment request. It is not `TextProvider`, chat completion, or JSON-generation mode. |
| `Choice` | A typed result selecting exactly one key from the finite option set declared by the versioned decision pack. |
| `Score` | A typed finite numeric result within the inclusive range declared by the versioned decision pack. |
| `Noul` | A typed non-decision/abstention result with a reason key declared by the decision pack. It is not `null`, a missing response, success, approval, or rejection. |
| Decision pack | A consumer-owned, versioned definition of question wording, allowed output kind and values, criteria, domain thresholds, failure handling, and evidence. |
| Admission | A separate governance decision allowing a provider/model/version for a bounded use. Catalog identity or capability evidence alone is not admission. |
| Baseline | The deterministic behavior that applies when judgment is absent, invalid, uncertain, denied, or unavailable. |

## Contract Requirements

### Separate Typed Interface

- **FR-001**: J1 MUST define `JudgmentProvider` as a separate typed interface.
- **FR-002**: The interface MUST NOT accept or return a text-generation/chat contract as its public judgment API.
- **FR-003**: Provider-specific wire formats MUST remain behind the interface and MUST NOT leak into consumer decision packs.
- **FR-004**: One invocation MUST evaluate one request and return either one validated result envelope or one normalized error.

### Typed Input

The future request contract MUST contain the following typed fields:

| Field | Required behavior |
| --- | --- |
| `decision_pack_id` | Non-empty stable identifier owned by the consumer. |
| `decision_pack_version` | Non-empty exact version; aliases such as `latest` are invalid. |
| `question_id` | Non-empty stable identifier within the decision pack. |
| `input_payload` | Structured consumer-prepared input; its schema is owned by the decision pack. |
| `expected_output` | Exactly one declared contract: choice keys, score bounds, or permitted Noul reason keys. |
| `data_class` and `outbound_form` | Explicit privacy inputs evaluated before transport; transformation does not silently lower classification. |
| `provider_id`, `model_id`, `model_version` | Exact selected identity and version values; wildcard and `*-latest` values are invalid for admitted behavior. |
| `total_deadline` | One positive total execution budget shared by policy checks, attempts, bounded retry, validation, and fallback. |
| `max_same_provider_retries` | Integer `0` or `1`; default `0`. It cannot expand the total deadline. |
| `correlation_id` | Opaque metadata identifier; it MUST NOT contain prompt or response payload. |

The request MUST NOT carry authority to admit a provider, authorize egress, override a protected gate, or define a threshold outside its referenced decision pack.

### Typed Output

The future result envelope MUST contain:

- the same `decision_pack_id`, `decision_pack_version`, and `question_id`;
- exact `provider_id`, `model_id`, and `model_version`;
- exactly one result variant: `Choice`, `Score`, or `Noul`;
- optional confidence only as a finite value in the inclusive range `[0, 1]`;
- metadata needed for correlation and bounded diagnostics, excluding request/response payloads.

Variant requirements:

| Variant | Required fields | Validation |
| --- | --- | --- |
| `Choice` | selected choice key; optional confidence | Key is present exactly once in the request's declared finite choice set. |
| `Score` | finite numeric value; optional confidence | Value is not boolean and lies within the request's inclusive declared bounds. |
| `Noul` | reason key; optional confidence | Reason key belongs to the decision pack's declared Noul reasons; no choice or score is present. |

### Validation Behavior

- **FR-005**: Request validation, catalog eligibility, privacy, and egress checks MUST complete before transport.
- **FR-006**: Unknown fields at the provider response boundary MUST be rejected unless a future versioned contract explicitly admits them.
- **FR-007**: Exactly one output variant MUST be present.
- **FR-008**: Invalid provider responses MUST never reach consumer decision logic.
- **FR-009**: Result metadata MUST match the request and actual selected provider/model/version exactly.
- **FR-010**: A missing confidence value MUST remain missing; it MUST NOT be manufactured or interpreted as positive evidence.
- **FR-011**: Validation failure MUST produce a provider-neutral normalized error and then apply the same deadline and fallback restrictions as every other attempt.

## Provider-Neutral Error Taxonomy

| Error kind | Meaning | Same-provider retry | Cross-provider fallback |
| --- | --- | --- | --- |
| `INVALID_REQUEST` | Request or decision-pack reference violates the typed contract. | No | No |
| `PRIVACY_DENIED` | Payload classification is not eligible. | No | No |
| `EGRESS_DENIED` | Required egress lacks explicit authorization/evidence. | No | No |
| `PROVIDER_NOT_ELIGIBLE` | Identity, capability, model, version, or admission gate failed. | No | Only after a separately eligible candidate passes all gates. |
| `AUTH` | Provider authentication or authorization failed. | No | No |
| `BAD_REQUEST` | Provider rejected a validly transported request as malformed. | No | No |
| `NOT_FOUND` | Exact admitted model/version is unavailable at that provider. | No | Yes |
| `RATE_LIMIT` | Provider rate limit, including future authorized `429` handling. | At most one | Yes |
| `TIMEOUT` | Attempt exceeded its allocated slice. | At most one | Yes |
| `SERVER` | Provider server failure, including future authorized `529` handling. | No | Yes |
| `TRANSPORT` | Network or protocol transport failure. | No | Yes |
| `PROVIDER_UNAVAILABLE` | Provider is unavailable before a usable response. | No | Yes |
| `INVALID_RESPONSE` | Response failed typed validation. | No | Yes, if policy permits. |
| `DEADLINE_EXHAUSTED` | The one total deadline has no safe remaining budget. | No | No |
| `UNKNOWN` | Failure cannot be safely classified. | No | No |

Errors MUST contain metadata only. They MUST NOT embed credentials, request payloads, raw provider responses, or protected instructions.

## Deadline, Retry, and Fallback Semantics

- **FR-012**: One monotonic total deadline MUST cover all attempts, the optional same-provider retry, response validation, and fallback.
- **FR-013**: A provider receives one initial attempt and at most one retry only when `max_same_provider_retries == 1` and the normalized error is `RATE_LIMIT` or `TIMEOUT`.
- **FR-014**: Retry MUST stop when the remaining deadline cannot safely fund another attempt.
- **FR-015**: Fallback order MUST be explicit and deterministic; nested provider-owned fallback is forbidden.
- **FR-016**: Every fallback candidate MUST independently pass identity, future `JUDGMENT` capability, admission, exact-version, health, privacy, and egress gates.
- **FR-017**: A local/no-egress policy MUST NOT fall back to a hosted provider.
- **FR-018**: Exhaustion or any non-fallback error returns a normalized failure; it MUST NOT synthesize `Choice`, `Score`, or `Noul`.

## Privacy and Egress

- **FR-019**: Privacy and egress enforcement MUST occur before any transport bytes, credential lookup, retry, or fallback.
- **FR-020**: `SECRET` data remains denied under the existing ai-core contract.
- **FR-021**: `typesafe_jev` is hosted and may receive only payloads classified `PUBLIC` or accompanied by contractual evidence that the transmitted payload is `ANONYMIZED`.
- **FR-022**: Sanitization or surrogation alone MUST NOT manufacture `ANONYMIZED` status or lower the original data classification.
- **FR-023**: ZDR MUST NOT be assumed. It may be claimed only when current contractual evidence is attached to the governance admission record.
- **FR-024**: `kev_local` is the planned local/no-egress provider. Its failure MUST NOT trigger hosted fallback.
- **FR-025**: Credentials and credential values are outside the request/result contract and MUST NOT appear in telemetry.

## Metadata-Only Telemetry

By default, judgment telemetry may record only:

- provider, model, and exact version identifiers;
- decision-pack ID/version and question ID;
- output kind, attempt count, retry/fallback occurrence, status, normalized error kind, and latency;
- privacy/egress gate outcome as a non-payload reason code;
- correlation ID.

Prompt/input payload, raw provider request, raw provider response, selected choice, numeric score, Noul reason, free-form explanation, credentials, and protected instructions MUST NOT be recorded by default. Any future payload telemetry requires a separate explicit authorization and privacy review; J1 does not authorize it.

## Authority Limits

No `JudgmentProvider`, result, confidence, threshold, or fallback may:

- execute or authorize a merge;
- authorize destructive commands or permissions;
- grant access or approve egress;
- hide or weaken protected instructions;
- auto-accept or auto-reject a legal, procurement, or business decision;
- modify legally significant data;
- send email, export data, or write to 1C;
- automatically merge entity or master-data records;
- mark work complete in place of deterministic completion checks;
- override a human gate or operator decision.

The result is advisory input only. Deterministic rules and required human review remain authoritative.

## Fail-Neutral / Fail-Closed Matrix

This matrix applies to error, timeout, invalid response, missing confidence, and confidence below the consumer-owned threshold.

| Decision surface | Required behavior | Mode |
| --- | --- | --- |
| Model or effort selection | Preserve baseline model and baseline effort. | Fail-neutral |
| Context filtering | Preserve the complete original context chunk. | Fail-neutral |
| Tool selection | Do not call the tool, or require human handoff. | Fail-closed |
| Egress, destructive action, access, or merge | Deny or require human review. | Fail-closed |
| Completion detection | Treat as incomplete; deterministic checks remain authoritative. | Fail-closed |
| Prozakupki review priority | Preserve the current queue. | Fail-neutral |
| On-prem document routing | Use `needs_review`; no hosted fallback. | Fail-closed |

## Catalog Integration Design

- **FR-026**: Future catalog eligibility MUST use a dedicated `JUDGMENT` capability.
- **FR-027**: `JUDGMENT` is a design choice in this specification only. It is absent from ai-core `v0.3.1` runtime and MUST NOT be added by this docs-only package.
- **FR-028**: Provider identity, `JUDGMENT` capability evidence, exact model/version admission, and consumer decision-pack approval are independent gates.
- **FR-029**: Capability evidence alone MUST NOT authorize execution or admission.
- **FR-030**: Thresholds MUST be keyed to and calibrated for the exact provider/model/version/decision-pack tuple. They MUST NOT be copied across tuples.

Planned provider implementations:

| Provider implementation | Intended boundary | Current status |
| --- | --- | --- |
| `typesafe_jev` | Hosted judgment provider | Planned; not admitted; not implemented |
| `kev_local` | Local/no-egress judgment provider | Planned; not admitted; not implemented |
| `mock_judgment` | Deterministic test-only provider | Planned; not admitted; not implemented |

## D7 Compatibility Baseline

The accepted D7 canon is:

> ai-core `v0.3.1` at `85c82f5` plus the platform-control issue `#291` extensions.

### Present in Runtime `v0.3.1`

Canonical provider identities:

- `vm100_local_ollama` (`LOCAL_SAME_HOST`)
- `gpu_ollama` (`UNKNOWN_BOUNDARY`)
- `ollama_cloud` (`EXTERNAL`)
- `mistral_external` (`EXTERNAL`)

Capabilities:

- `TEXT`
- `STRUCTURED_JSON`
- `VISION_IMAGE`
- `OCR_PDF`

Migration aliases:

- `ollama_local` → `vm100_local_ollama`
- `local_gpu_ollama` → `gpu_ollama`
- `local_gpu_vision` → `gpu_ollama`
- `mistral` → `mistral_external`
- `mistral_ocr` → `mistral_external`

### Accepted in Canon, Implementation Pending

The following are canonical with status **accepted-in-canon, implementation pending**:

- provider identity `gpu_whisper` (`UNKNOWN_BOUNDARY`);
- provider identity `openai_external` (`EXTERNAL`);
- provider identity `deepseek_external` (`EXTERNAL`);
- capability `STT_SEGMENTS`;
- migration alias `local_gpu_whisper` → `gpu_whisper`.

Issue `#291` also reaffirms the already-present aliases `local_gpu_ollama`, `local_gpu_vision`, `mistral`, and `mistral_ocr`. Generic `ollama` deliberately remains ambiguous and fail-closed.

These extensions are not present in runtime `v0.3.1`, are not released or admitted by this specification, and do not block the future J1 `JudgmentProvider` contract.

## J1 Acceptance Criteria

J1 is accepted only when a separately authorized implementation PR demonstrates all of the following:

- **J1-AC-001**: `JudgmentProvider` is a separate typed interface and has no TextProvider/chat/JSON-mode substitution.
- **J1-AC-002**: `Choice`, `Score`, and `Noul` request/response validation has deterministic contract tests for valid and invalid cases.
- **J1-AC-003**: Invalid responses reaching consumer decision logic: `0`.
- **J1-AC-004**: Denied privacy/egress cases producing transport calls: `0`.
- **J1-AC-005**: Prompt/response payload fields recorded by default telemetry: `0`.
- **J1-AC-006**: All retry and fallback attempts stay inside one total deadline, with no nested fallback.
- **J1-AC-007**: Local/no-egress cases producing hosted fallback calls: `0`.
- **J1-AC-008**: Every authority-limit test preserves deterministic or human control.
- **J1-AC-009**: `mock_judgment` tests the interface without real credentials or network calls and remains test-only.
- **J1-AC-010**: Exact-head human review confirms catalog and compatibility behavior; release remains a separate decision.

## Explicit J2 and Later Scope

The following are outside J1 and require separate authorization:

- `typesafe_jev` and `kev_local` adapters or stubs that can make real calls;
- SDK installation, credentials, endpoints, contractual ZDR claims, or network integration;
- labelled datasets, offline evaluation, calibration, and baseline comparison;
- consumer integration or migration;
- shadow execution, live execution, deployments, or provider admission;
- any release, tag, or broad capability rollout.

## Assumptions and Dependencies

- ADR-023 and the semantic judgment pilot remain proposed/plan-only until a later operator gate.
- Platform-control owns governance, admission, privacy policy, protected gates, and evidence requirements.
- ai-core owns only the future provider-neutral contract and bounded execution boundary.
- Consumers own decision packs, domain thresholds, datasets, deterministic rules, and human-review workflows.
- The unratified constitution template introduces no additional process gate.
