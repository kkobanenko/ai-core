# Feature Specification: Judgment Provider v0.1

**Status**: PLAN_ONLY — documentation defines a future contract; it does not
authorize runtime, provider admission, deployment, credentials, network calls,
consumer migration, or automatic actions.

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

- This package does not add runtime code, a `JUDGMENT` enum value, catalog
  entries, provider identities, aliases, SDKs, credentials, endpoints, or
  network integration.
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
| **Choice** | A finite, decision-pack-defined symbolic outcome. The provider may select only one declared choice. |
| **Score** | A bounded numeric assessment with declared scale and meaning. A score is evidence, not authorization. |
| **Noul** | A typed neutral/unknown result that states the provider cannot produce a usable judgment. It is not a hidden fallback, inferred approval, or missing field. |
| **decision pack** | A consumer-owned, versioned definition of question, allowed choices, score semantics, criteria, thresholds, deterministic rules, and evaluation evidence. |
| **admitted behavior** | A provider/model/version/decision-pack combination accepted by a separate governance decision for a bounded use. |

## Future typed contract

The future interface accepts a `JudgmentRequest` and returns a
`JudgmentResponse`; implementations must not expose free-form provider text as
the contract result.

### Request

`JudgmentRequest` contains:

- immutable `request_id` for correlation;
- exact `decision_pack_id` and `decision_pack_version`;
- a bounded question or criterion identifier defined by that decision pack;
- declared allowed `Choice` values, score scale, and whether `Noul` is allowed;
- a classified payload and explicit egress authorization input;
- a total monotonic deadline covering the whole invocation;
- an exact provider/model/version selection when one has been admitted.

Validation rejects an empty identifier, duplicate choices, an undeclared score
scale, an unknown decision-pack version, an invalid classification, an
unbounded or expired deadline, and any provider/model/version selector that is
not exact. A request never accepts `*-latest` for admitted behavior.

### Response

`JudgmentResponse` contains exactly one result variant:

- `choice`: one allowed `Choice`, with any required bounded `Score`;
- `noul`: an explicit neutral/unknown reason code; or
- `error`: a provider-neutral error classification.

It also contains the exact provider identity, model, model version, decision
pack identifier/version, and non-payload execution metadata needed for
validation. A successful choice must be declared by the request; a score must
be finite and within the declared scale; a `Noul` must carry no implied
choice. Invalid, incomplete, incompatible, or unparseable provider output is
rejected before it reaches consumer logic.

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
another combination. Provider unavailability or low confidence preserves the
relevant baseline rather than manufacturing a more favorable result.

### Privacy, egress, telemetry, and version pinning

Privacy and egress eligibility are evaluated before transport construction,
credential lookup, retry, or fallback. Hosted `typesafe_jev` may receive only
`PUBLIC` data or data confirmed as `ANONYMIZED` by applicable evidence. Zero
data retention is not assumed without contractual evidence. `kev_local` is the
local/no-egress option for sensitive data.

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

| Decision surface | Error, timeout, invalid response, `Noul`, or low confidence |
| --- | --- |
| Model or effort selection | Preserve the baseline model and baseline effort. |
| Context filtering | Preserve the complete original context chunk. |
| Tool selection | Do not call the tool; require human handoff where applicable. |
| Egress, destructive action, access, or merge | Deny or require human review. |
| Completion detection | Treat as incomplete; deterministic checks remain authoritative. |
| Prozakupki review priority | Preserve the current queue. |
| On-prem document routing | Use `needs_review`; no hosted fallback. |

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

The D7 canonical provider set is **ai-core v0.3.1 plus pc#291 extensions**.
The extensions `gpu_whisper`, `openai_external`, `deepseek_external`,
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

- A typed `JudgmentProvider`, `Choice`, `Score`, and `Noul` contract validates
  requests and responses without treating text/JSON generation as the result.
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
- Failure tests prove every row of the fail-neutral/fail-closed matrix.

### Explicit J2 and later scope

Provider adapters for `typesafe_jev` or `kev_local`, their SDKs and
credentials, real network calls, offline evaluation, calibrated thresholds,
consumer integration, provider admission, deployment, and per-decision-pack
admission are outside J1. They require separate authorization and evidence.
