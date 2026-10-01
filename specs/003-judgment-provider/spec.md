# Feature Specification: Judgment Provider v0.1

**Status**: J1 `contract_only` — ai-core implements the provider-neutral typed
contract, validation, privacy boundary, deadline runtime, metadata telemetry,
and deterministic `mock_judgment`. It does not authorize catalog promotion,
provider admission, deployment, credentials, network calls, or consumer migration.

## Problem statement

Consumers need a bounded, typed semantic-judgment signal for advisory decisions
without treating text generation, JSON mode, or any hosted provider as an
authority. The future `judgment_provider_v0_1` contract makes that signal
replaceable and validates it before consumer logic can observe it.

The contract must preserve deterministic business rules, human review, and
existing baselines when a provider is unavailable, late, invalid, or
low-confidence. It must also enforce privacy and egress before any transport
attempt.

## Non-goals

- J1 does not add a `JUDGMENT` catalog capability, catalog entries, provider
  identities, aliases, SDKs, credentials, endpoints, or network integration.
- A `JudgmentProvider` is not a `TextProvider`, prompt-to-JSON convention, or
  a mode of structured text generation.
- It does not admit `typesafe_jev`, `kev_local`, or `mock_judgment` as a live
  provider, change consumer decisions, or create a release.
- It does not define domain thresholds, decision-pack criteria, labelled data,
  durable workflow retries, or human-review policy.
- It does not grant authority to merge, perform destructive actions or egress,
  grant access, accept legal or business terms, or override completion status.

## Glossary

| Term | Meaning |
| --- | --- |
| **JudgmentProvider** | A future typed interface that receives a validated judgment request and returns a validated judgment response. It is separate from text completion. |
| **BinaryQuestion / BinaryAnswer** | Provider-neutral boolean judgment. `BinaryAnswer.probability_true` is a finite float in `[0, 1]`; ai-core never auto-converts it to `bool`. Thresholds belong to the consumer. |
| **ChoiceQuestion / ChoiceAnswer** | Finite declared choices, one selected choice, confidence in `[0, 1]`, and a probability distribution over exactly all declared choices summing to approximately `1`. |
| **ScoreQuestion / ScoreAnswer** | Declared score bounds and levels; `expected_score` within bounds; confidence and a level probability distribution summing to approximately `1`. |
| **Provider adapter terms (e.g. Jev Noul)** | Mapping-only concepts for future adapters. They are not exposed as provider-neutral ai-core domain types in J1. Uncertainty is represented via probabilities/confidence or normalized execution errors. |
| **decision pack** | A consumer-owned, versioned definition of question, allowed choices, score semantics, criteria, thresholds, deterministic rules, and evaluation evidence. |
| **admitted behavior** | A provider/model/version/decision-pack combination accepted by a separate governance decision for a bounded use. |

## Future typed contract

The future interface accepts a `JudgmentRequest` and returns a
`JudgmentResponse`; implementations must not expose free-form provider text as
the contract result.

### Request (batch-first)

`JudgmentRequest` contains:

- immutable `request_id`;
- exact `decision_pack_id` and `decision_pack_version`;
- provider-neutral `shared_state` (string map validated locally);
- named `questions`: `question_name -> JudgmentQuestion` where
  `JudgmentQuestion = BinaryQuestion | ChoiceQuestion | ScoreQuestion`;
- at least one non-empty unique question name;
- `DataClass`, `OutboundForm`, explicit egress authorization input, and
  `JudgmentExecutionMode` (`local_no_egress` vs `hosted_egress`);
- one total monotonic deadline for the whole batch;
- exact `provider_id`, `model`, and `model_version` pins (no wildcards or
  `*-latest` aliases).

Validation rejects empty identifiers, invalid shared state, empty question
maps, invalid classifications, expired deadlines, and non-exact pins before
any provider invocation.

### Response (successful)

A successful `JudgmentResponse` contains:

- `answers`: `question_name -> JudgmentAnswer` with exactly one answer per
  requested question and no extras;
- answer variant must match the question variant;
- exact provider/model/version metadata and non-payload execution metadata.

Execution failure is represented only through normalized judgment errors, not
by fabricating partial business answers. Provider free-form/raw text never
crosses into the consumer-visible contract.

### Provider-neutral error taxonomy

The future contract normalizes errors into these stable categories:

| Category | Meaning | Retry/fallback posture |
| --- | --- | --- |
| `invalid_request` | The request fails local contract validation. | Terminal; no transport. |
| `privacy_egress_denied` | Data class, egress authorization, or provider boundary is ineligible. | Terminal; no transport. |
| `deadline_exhausted` | The common total deadline has no remaining attempt budget. | Terminal. |
| `rate_limited` | Provider reports a retryable rate limit. | A bounded retry is possible only inside the common deadline. |
| `authentication_failed` | Provider authentication is rejected. | Terminal for that provider; no credential mutation. |
| `provider_unavailable` | Provider is unavailable or temporarily unhealthy. | Bounded, policy-permitted fallback only. |
| `transport_failed` | Connection, protocol, or timeout failure. | Bounded, policy-permitted fallback only. |
| `invalid_provider_response` | Provider output violates the typed response contract. | Fail neutral or closed; no consumer parsing fallback. |
| `internal_error` | An unexpected local failure. | Fail neutral or closed; never auto-approve. |

## Execution semantics

### Deadline, retry, and fallback

One monotonic total deadline governs validation, bounded retries, and every
eligible fallback attempt. A retry must consume remaining budget, be explicitly
bounded, and must not nest inside a transport or adapter. Future handling of
429 and 529 is inside this same deadline.

Fallback is possible only after contract validation, privacy/egress gating,
and a policy decision for the same decision pack. `kev_local` has no hosted
fallback. Provider/model/version/decision-pack thresholds are never copied to
another combination. Within ai-core, provider unavailability yields typed
errors or bounded fallback per policy; it does not assert consumer baselines
(see **Deferred beyond J1**).

### Privacy, egress, telemetry, and version pinning

Privacy and egress eligibility are evaluated before transport construction,
credential lookup, retry, or fallback. Hosted `typesafe_jev` may receive only
`DataClass.SYNTHETIC` and `DataClass.PUBLIC_NO_PII` from
`src/ai_core/privacy.py`. All other `DataClass` values are local-only or
denied. The typed anonymization mapping is deferred to Wave C and is not
defined here. Zero data retention is not assumed without contractual evidence.
`kev_local` is the local/no-egress option for sensitive data.

Telemetry is metadata-only by default: outcome, normalized error category,
latency, retry count, provider identity, exact model/version, and decision-pack
identifier/version are permitted. Prompts, responses, payload fragments,
credentials, and decision-pack payload values are prohibited from telemetry by
default.

Every admitted behavior pins an exact model and version. `typesafe_jev`, if
separately admitted, uses `jev-1.13.0`; `jev-latest` is forbidden. Its Python
SDK floor is `0.7.1` for that future adapter only. `kev_local` requires its own
separate version admission. A pin does not itself admit a provider.

### Authority limits

Neither the provider result nor any provider implementation may:

- merge changes or authorize destructive commands, egress, or access;
- hide protected instructions or replace deterministic completion checks;
- automatically accept or reject a procurement or legal/business decision;
- modify legally significant data, send email, export/write to 1C, or
  auto-merge entity/master-data records;
- convert a missing confidence or `Noul` into approval or a lower review level.

## Fail-neutral and fail-closed behavior

### J1 ai-core contract boundary

J1 proves only what ai-core returns after validation and execution: a typed
batch `JudgmentResponse` or provider-neutral `error`. ai-core does not read or mutate
consumer queues, routing labels, model/effort selectors, or context filters.
On failure, ai-core is fail-closed: invalid input and invalid provider output
never reach consumer callbacks; privacy/egress denial occurs before transport;
and no result variant grants merge, egress, access, or automatic approval.

J1 failure tests cover contract validation, normalized error categories,
deadline exhaustion, `invalid_provider_response`, and metadata-only telemetry —
not consumer decision surfaces.

### Fail-neutral protocol for consumers (post-J1)

Consumers that integrate judgment results apply their own fail-neutral rules
outside ai-core. ai-core supplies the typed result or error; the consumer
decides review, routing, tool use, and queue changes. The table below is
reference design for that later protocol; J1 does not runtime-test these rows.

| Decision surface | Error, timeout, invalid response, or low-confidence signal (consumer applies) |
| --- | --- |
| Tool selection | Do not call the tool; require human handoff where applicable. |
| Egress, destructive action, access, or merge | Deny or require human review. |
| Completion detection | Treat as incomplete; deterministic checks remain authoritative. |
| Prozakupki review priority | Preserve the current queue. |

### Deferred beyond J1

The following were removed from the J1 verification scope per platform
remark **C7** and **architect response #6** (AI-JUDGMENT-J010-BOUNDARY-01).
They remain documented for a later increment; they are not deleted from the
overall judgment design.

| Deferred item | Intended post-J1 behavior (consumer-owned) |
| --- | --- |
| Model, effort, and context selection | On judgment failure or insufficient information, preserve baseline model, baseline effort, and the complete original context chunk. |
| `needs_review` routing state | On-prem document routing sets or preserves `needs_review`; no hosted fallback. |
| Low-confidence routing and handling | Low-confidence outcomes preserve declared baselines and avoid manufacturing a more favorable result; routing follows consumer policy, not ai-core tests. |

## Planned catalog integration

Future catalog eligibility is designed around a distinct `JUDGMENT` capability.
It is a design choice for a later authorized J1 implementation, not a current
runtime capability. The catalog must continue to require identity, exact model,
capability authorization, privacy/egress eligibility, health, and governance
admission; `JUDGMENT` alone must not make a provider eligible.

The proposed implementations are `typesafe_jev`, `kev_local`, and
`mock_judgment`. All are planned, unadmitted, and unimplemented. The mock is
test-only and is not a production provider.

## D7 compatibility statement

The D7 canonical provider set, recorded as operator decision D7
(judgment provider canon, platform-control ADR-024, merged in
platform-control #338), is **ai-core v0.3.1 plus pc#291 extensions**. The
extensions `gpu_whisper`, `openai_external`, `deepseek_external`,
`STT_SEGMENTS`, and the pc#291 migration aliases are
**accepted-in-canon, implementation pending**. They are canonical
documentation inputs only in this package and do not block
`judgment_provider_v0_1`.

### Present in v0.3.1 runtime

| Runtime item | Current state |
| --- | --- |
| Provider identities | `vm100_local_ollama`, `gpu_ollama`, `ollama_cloud`, `mistral_external` |
| Capability vocabulary | `TEXT`, `STRUCTURED_JSON`, `VISION_IMAGE`, `OCR_PDF` |
| Aliases | `ollama_local` → `vm100_local_ollama`; `local_gpu_ollama` and `local_gpu_vision` → `gpu_ollama`; `mistral` and `mistral_ocr` → `mistral_external` |
| Generic `ollama` | Rejected as ambiguous/fail-closed |
| Existing default external model reference | `mistral-small-latest`; this is existing runtime behavior, not a J1 admission or a precedent for future admitted judgment behavior |

### Accepted canon, implementation pending

| Canonical extension | Required documentation status |
| --- | --- |
| `gpu_whisper` | `UNKNOWN_BOUNDARY`; RAW private data denied |
| `openai_external` | `EXTERNAL_CLOUD`; RAW private data denied |
| `deepseek_external` | `EXTERNAL_CLOUD`; RAW private data denied |
| `STT_SEGMENTS` | First-class future model capability |
| `local_gpu_whisper` → `gpu_whisper` | Migration alias |
| `local_gpu_ollama` → `gpu_ollama`; `local_gpu_vision` → `gpu_ollama`; `mistral`/`mistral_ocr` → `mistral_external` | Retained migration aliases |
| generic `ollama` | Remains ambiguous and fail-closed |

No extension in this table is asserted to exist in the current runtime. The
current v0.3.1 runtime catalog and enum remain unchanged by this documentation
package.

## Acceptance boundary

### J1 acceptance criteria for a separately authorized implementation PR
(`AUTHORIZE_J1`, scope `contract_only`; current state `HOLD_J1`)

- A typed `JudgmentProvider` and provider-neutral `Binary` / `Choice` / `Score`
  batch contract validates requests and responses without treating text/JSON
  generation as the result.
- Contract tests prove invalid inputs and invalid provider responses cannot
  reach consumer logic.
- Privacy/egress tests prove the gate runs before transport, credential lookup,
  retry, and fallback.
- Deadline tests prove retries and any fallback share one bounded total
  deadline.
- Serialization and metadata-only telemetry tests prove no prompt/response
  payload is emitted by default.
- A future `JUDGMENT` capability is eligible only through all existing catalog
  gates and separate governance admission.
- Failure tests prove J1 ai-core fail-closed behavior (validation rejects
  bad input/output before consumers observe a result; privacy gate ordering;
  no automatic approval from errors or mock fixtures). They do not
  assert consumer model/effort/context, `needs_review`, or low-confidence
  routing (see **Deferred beyond J1**).

### Explicit J2 and later scope

Provider adapters for `typesafe_jev` or `kev_local`, their SDKs and
credentials, real network calls, offline evaluation, calibrated thresholds,
consumer integration, provider admission, deployment, and per-decision-pack
admission are outside J1. Consumer integration, the fail-neutral protocol
rows above, and all **Deferred beyond J1** items are intentionally deferred
until after J1. These areas require separate authorization and evidence.
