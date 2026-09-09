# AI Core Governance Decision Packets

**Evidence date:** 2026-09-09 (Europe/Moscow)
**Package status:** decision support only
**Decision status:** every packet and subdecision is `OPEN`
**Implementation authorization:** none

## 1. How to use this document

This document recommends a minimal safe foundation. It does not accept an ADR,
resolve a `pending_decision`, authorize runtime work, or modify platform-control.

Labels used below:

- **FACT:** directly observed in a pinned file, commit, API result, or test;
- **INFERENCE:** conclusion from one or more facts;
- **RECOMMENDATION:** proposed operator/platform-control choice;
- **OPEN:** no approval evidence exists yet.

An operator decision is valid only when recorded through the applicable
platform-control governance path. A recommendation in this branch is not that
record.

## 2. Refreshed evidence ledger

| ID | Strength | Evidence observed on 2026-09-09 |
|---|---|---|
| E1 | FACT | GitHub `ai-core/main` is `7569441c18362cfd15524ad73f56f7f35580c86f`; local main matches. |
| E2 | FACT | GitHub `platform-control/main` is `6445a2ed8614ae0bb663b92413ebf04f3fbc1d99`. Its `config/compatibility.yaml` still records observed `ai_core_main_sha: 83acc5304bd87451a0dc96d7a3b0ca663ec6769f`. |
| E3 | FACT | The same platform-control revision lists `ai-core-v0.3-design` as `rfc_only`, records `main_sha: 7569441...`, sets `ai_core_v0_3_implementation_authorized: false`, and prohibits `ai_core_v0_3_implementation`. |
| E4 | FACT | Platform-control issues [#291](https://github.com/kkobanenko/platform-control/issues/291), [#292](https://github.com/kkobanenko/platform-control/issues/292), and [#293](https://github.com/kkobanenko/platform-control/issues/293) are OPEN with no comments, labels, or approval record. Their bodies say they are review requests only. |
| E5 | FACT | AI Core PR [#3](https://github.com/kkobanenko/ai-core/pull/3) at `4e26d67...`, PR [#4](https://github.com/kkobanenko/ai-core/pull/4) at `1b2569a...`, and PR [#5](https://github.com/kkobanenko/ai-core/pull/5) at `25c269b...` remain OPEN, DRAFT, mergeable, CI-green, and without approving review. |
| E6 | FACT | Current `main` exports the nine-symbol tracing contract. PR #3 adds three dependency-light provider-policy modules without changing root exports or dependencies. |
| E7 | FACT | Characterization proves PR #3 denies `SECRET + RAW` but allows `SECRET + SANITIZED` and `SECRET + SURROGATED` for all four profiles. |
| E8 | FACT | PR #5 treats absent `authorized_provider_ids` as all catalog providers, sorts by catalog priority rather than request order, and treats `UNKNOWN` health as healthy. |
| E9 | FACT | Nine pinned consumer infrastructure contracts verify. Consumer-local provider names, model configuration, and HTTP client shapes are observations, not canonical acceptance. |
| E10 | FACT | Historical PR #2 has 85 mocked-HTTP tests. Mistral OCR live invocation succeeded. Ollama endpoint normalization/reachability succeeded. GPU vision returned HTTP 503 during a live attempt. |
| E11 | INFERENCE | Mistral OCR has runtime-observed evidence for that exact tested path. Ollama result proves endpoint normalization/reachability only. GPU vision 503 is a failed/inconclusive runtime-validation attempt and cannot raise model capability evidence. |
| E12 | FACT | `transcription-service` and `image-description-service` clients use separate media endpoints, service-key auth, 150-second client timeouts, and consumer-owned durable attempts. No canonical AI Core server exists. |

### Governance drift classification

Platform-control contains two different AI Core pointers at the same revision:

- stale observed compatibility pointer: `83acc530...`;
- current initiative pointer and factual GitHub main: `7569441...`.

This remains **GOVERNANCE OBSERVED-STATE DRIFT**. It does not change production
state, but any future governance record must use `7569441...` or a later freshly
verified main. This package does not repair platform-control.

## 3. Capability evidence language

| Level | Meaning | May affect automatic production routing? |
|---|---|---|
| `CONFIGURED` | Provider/model/capability appears in config or documentation. No executable proof. | No. |
| `UNIT_TESTED` | Deterministic code path passes isolated tests, normally with mocks/fakes. | No. |
| `INTEGRATION_TESTED` | Real protocol integration succeeds against controlled service/environment with recorded provider, model, capability, boundary, and result. | Shadow/non-production only by default. |
| `RUNTIME_OBSERVED` | Successful real invocation of exact provider/model/capability at named boundary, with timestamp and safe evidence. | Candidate only after privacy, identity, health, and governance gates also pass. |
| `FAILED_INCONCLUSIVE` | A real attempt failed without proving whether model capability exists. | No; never promotes evidence. |

Evidence is attached to `(provider identity, model, capability, network
boundary)`, not provider identity alone. `FAILED_INCONCLUSIVE` is an outcome
marker, not an ordinal level above `INTEGRATION_TESTED`.

---

## D1 — Baseline and additive foundation boundary

**Question**

May AI Core add a dependency-light canonical foundation in submodules while
keeping the exact root tracing API unchanged, and which main SHA governs it?

**Why it matters**

Without an accepted boundary, even pure provider types can silently turn the
RFC-only initiative into unauthorized v0.3 implementation. A stale SHA also
makes review and rollback ambiguous.

**Current evidence**

- **FACT:** E1-E6 establish factual main, governance drift, RFC-only status,
  exact root compatibility, and draft foundation content.
- **FACT:** platform-control already accepts tracing/provider types/configuration
  as target concepts, but explicitly withholds v0.3 implementation authority.
- **INFERENCE:** current accepted language supports reviewing an additive
  foundation but does not authorize merging one.

**Recommended decision**

Approve, through platform-control, a narrowly additive foundation based on
freshly recorded `ai-core/main@7569441...` or later reviewed main:

- exact nine-symbol root `ai_core.__all__` remains unchanged;
- tracing import path remains dependency-light;
- new contracts live only in explicit submodules;
- no provider SDK, HTTP client/server, transport, executor, or consumer runtime
  enters foundation;
- governance pointer reconciliation occurs in a separate platform-control
  change before merge authorization.

**Alternatives**

1. Keep AI Core tracing-only and leave all provider policy consumer-owned.
2. Adopt the historical v0.2.x package wholesale.
3. Allow root exports or mandatory transport dependencies in foundation.

**Consequences of recommended choice**

- Small compatibility surface; Zoom/Clin-rec dependency conflicts stay isolated.
- Provider/privacy types can be tested without choosing runtime architecture.
- Requires explicit platform-control record and pointer repair before merge.

**Consequences of alternatives**

- Tracing-only avoids new shared risk but preserves duplicated consumer logic.
- Wholesale v0.2.x import breaks current dependency and root-API boundaries.
- Root/dependency expansion raises consumer breakage and rollback cost.

**What remains deferred**

Concrete model routes, transports, executor, HTTP service, consumer migration,
release, deployment, and every D2-D6 policy choice.

**Effect on PR #3 / #4 / #5**

- PR #3: allows only isolated, corrected foundation candidates.
- PR #4: no new identity/capability approval.
- PR #5: no routing/execution approval.

**What this unlocks**

A reviewable foundation-only work package after D2/D3 decisions and formal
platform-control approval.

**Required authority**

Operator decision plus platform-control review/update. AI Core maintainer review
still required for merge.

**Status:** `OPEN`

---

## D2 — Privacy, all-form SECRET, and explicit egress

**Question**

Must `SECRET` be denied for every outbound form and boundary, and must missing
request-level egress authorization produce no external/unknown-boundary route?

**Why it matters**

Transformation labels can otherwise become a policy bypass. Implicit provider
authorization also converts missing security data into outbound permission.

**Current evidence**

- **FACT:** accepted compatibility language says `SECRET` disposition is
  `DROP_BLOCK` and LLM egress is forbidden by default.
- **FACT:** E7 proves PR #3 violates this for sanitized/surrogated `SECRET`.
- **FACT:** E8 proves PR #5 interprets a missing allowlist as all catalog IDs.
- **INFERENCE:** both behaviors are fail-open relative to intended invariant.

**Recommended decision**

- Evaluate `SECRET` denial before alias resolution, transformation, capability,
  health, ordering, retry, or fallback.
- `SECRET` always yields zero eligible routes and zero provider attempts for
  `RAW`, `SANITIZED`, and `SURROGATED`, at every network boundary.
- Sanitization/surrogation never reclassifies `SECRET`; a non-secret new request
  requires explicit upstream classification and policy evidence.
- Missing request-level egress authorization means no external or
  unknown-boundary route. No catalog-wide implicit default.
- Provider fallback may use only candidates authorized for that exact request.

**Alternatives**

1. Permit sanitized/surrogated `SECRET` to selected providers.
2. Treat absent egress allowlist as all providers allowed by catalog policy.
3. Let each consumer define its own SECRET semantics.

**Consequences of recommended choice**

- Removes transformation, alias, retry, and fallback bypass classes.
- Some requests fail closed until caller supplies complete classification and
  egress policy.
- Requires PR #3 privacy and PR #5 authorization redesign.

**Consequences of alternatives**

- Options 1-2 create silent data-exfiltration risk.
- Consumer-local semantics recreate inconsistent platform policy and make shared
  fallback unsafe.

**What remains deferred**

Sanitizer implementation, DLP implementation, domain classification, consent,
consumer data mapping, and transport enforcement.

**Effect on PR #3 / #4 / #5**

- PR #3: `is_eligible_for_outbound` must be redesigned for all-form denial.
- PR #4: aliases/evidence cannot weaken classification.
- PR #5: `authorized_provider_ids=None -> all` and inherited privacy behavior
  must be rejected/redesigned.

**What this unlocks**

Fail-closed privacy contract tests and later route-planning review.

**Required authority**

Operator and platform-control privacy/egress approval.

**Status:** `OPEN`

---

## D3 — Provider identities, evidence, and STT/vision/OCR capabilities

**Question**

Which provider identities are canonical, what evidence may affect routing, and
should STT/vision/OCR enter the accepted capability set now?

**Why it matters**

Provider identity defines network/security ownership; model capability defines
what exact deployment can do. Combining them or promoting config to runtime
proof makes routing claims unsafe.

**Current evidence**

- **FACT:** current accepted set contains `vm100_local_ollama`, `ollama_cloud`,
  `gpu_ollama`, and `mistral_external`.
- **FACT:** PR #4 proposes `gpu_whisper`, `openai_external`,
  `deepseek_external`, and `STT_SEGMENTS` without approval.
- **FACT:** PR #4's `CURRENT_OBSERVED` includes configuration references and
  therefore conflates configured state with runtime proof.
- **FACT:** E10-E11 distinguish successful Mistral OCR, Ollama reachability, and
  inconclusive GPU vision 503.
- **FACT:** consumer requirements include STT and vision but do not establish
  canonical acceptance.

**Recommended decision**

- Keep accepted provider set at four IDs for foundation.
- Preserve provider identity separately from `(model, capability, boundary)`
  evidence.
- Adopt evidence language in section 3.
- Require `RUNTIME_OBSERVED` evidence before a capability can join automatic
  production routing; allow `INTEGRATION_TESTED` only for explicit shadow or
  non-production evaluation.
- Treat Mistral OCR live success as exact-path `RUNTIME_OBSERVED`, not proof of
  every Mistral model/capability.
- Treat Ollama normalization/reachability as reachability-only.
- Treat GPU vision HTTP 503 as `FAILED_INCONCLUSIVE`; do not raise capability
  level.
- Defer new provider IDs and `STT_SEGMENTS` to separate governed packages.

**Alternatives**

1. Accept all PR #4 identities and capabilities based on consumer config.
2. Permit `INTEGRATION_TESTED` evidence in automatic production routes.
3. Treat capability as provider-wide rather than model-specific.

**Consequences of recommended choice**

- Foundation remains compatible and evidence claims remain auditable.
- STT/OpenAI/DeepSeek/GPU Whisper integration waits for explicit decisions.
- Mistral OCR may inform a later governed capability packet, not current merge.

**Consequences of alternatives**

- Config-driven acceptance routes to unavailable or untrusted deployments.
- Provider-wide claims incorrectly transfer evidence across models/modalities.
- Broad identity acceptance expands credentials, privacy, and operational scope.

**What remains deferred**

Identity approval for `gpu_whisper`, `openai_external`, `deepseek_external`;
`STT_SEGMENTS`; model recency/expiry; production probes; quotas; transports.

**Effect on PR #3 / #4 / #5**

- PR #3: four-ID type/catalog subset can remain a candidate; concrete capability
  profiles need evidence review.
- PR #4: evidence enum and profiles require redesign; new IDs/STT split out.
- PR #5: routing cannot consume unaccepted profiles or insufficient evidence.

**What this unlocks**

Four-ID foundation review and separate evidence-registration work package.

**Required authority**

Operator and platform-control provider/capability approval. New identities and
STT each require explicit separate acceptance.

**Status:** `OPEN`

---

## D4 — Routing, health, order, and three retry layers

**Question**

Who supplies route order; how is `UNKNOWN` health handled; and which layer owns
provider-call retry, provider fallback, and durable job/workflow retry?

**Why it matters**

Hidden global priority changes caller policy. Treating unknown health as healthy
creates unproven routes. Combining retry layers multiplies attempts and can
violate deadline, privacy, and idempotency guarantees.

**Current evidence**

- **FACT:** consumers use different provider orders and fallback owners.
- **FACT:** PR #5 discards caller order by sorting on catalog `priority_hint`,
  provider ID, and model.
- **FACT:** PR #5 treats unobserved provider/model health as eligible.
- **FACT:** service consumers own durable `max_attempts=3`; this is not a
  provider-attempt policy.
- **INFERENCE:** one universal retry contract cannot represent all three layers.

**Recommended decision**

Route ordering:

- caller supplies an explicit ordered candidate set constrained by D2/D3;
- AI Core preserves caller order after policy/capability/health filtering;
- provider/model lexical order is only a deterministic tie-break inside an
  explicitly equal policy rank;
- catalog priority is advisory metadata, never hidden global override.

Health:

- `UNKNOWN` is ineligible for normal automatic production routing;
- explicit bounded exploration may allow it only for non-secret,
  policy-authorized payloads, with named opt-in and no automatic evidence
  promotion;
- provider and model health remain isolated.

Retry ownership:

- **provider-call retry:** repeats same provider/model call for narrowly
  classified transient failure; future AI Core execution layer may own it;
- **provider fallback:** moves to next already-authorized candidate; same future
  AI Core execution layer may orchestrate it;
- **durable job/workflow retry:** restarts/resumes domain workflow and remains
  consumer-owned;
- one execution owner per bounded request; nested provider fallback forbidden;
  durable retry must create a new bounded request with a new deadline.

**Alternatives**

1. Global catalog priority overrides request order.
2. `UNKNOWN` is eligible by default.
3. Consumer owns provider loop while AI Core transport also falls back.
4. AI Core owns durable job retry.

**Consequences of recommended choice**

- Preserves explicit product policy and prevents attempt multiplication.
- Cold/unproven providers do not enter production automatically.
- Consumers retain queue, idempotency, persistence, and workflow responsibility.
- Future execution API must expose attempt/fallback results without controlling
  durable jobs.

**Consequences of alternatives**

- Hidden ordering produces consumer behavior drift.
- Default-eligible unknown health routes to unverified endpoints.
- Nested fallback multiplies calls and breaks shared deadlines.
- AI Core durable retry would absorb domain state and service persistence.

**What remains deferred**

Retry counts, backoff/jitter, circuit breaker, health probe transport, executor,
idempotency keys, consumer queue policy, and telemetry.

**Effect on PR #3 / #4 / #5**

- PR #3: `priority_hint` cannot be authoritative behavior.
- PR #4: evidence/aliases do not determine order or health.
- PR #5: ordering and `UNKNOWN` eligibility require fixes; planning types may be
  retained only after those decisions.

**What this unlocks**

Route-plan contract work followed by a separately authorized execution design.

**Required authority**

Operator and platform-control routing/fallback approval; each consumer confirms
durable retry ownership during later migration planning.

**Status:** `OPEN`

---

## D5 — Canonical errors and one end-to-end deadline

**Question**

Which errors govern retry/fallback, and how does one deadline bound service
overhead, attempts, waits, and fallback?

**Why it matters**

Transport-only error categories omit policy/schema failures. Independent
timeouts let nested attempts exceed caller budget.

**Current evidence**

- **FACT:** PR #5 defines timeout, rate-limit, auth, bad-request, not-found,
  server, transport, deadline, unavailable, and unknown kinds.
- **FACT:** it uses class-name heuristics and lacks explicit privacy/policy,
  capability, and schema/contract categories.
- **FACT:** its pure `AttemptBudget` correctly uses monotonic arithmetic and can
  reserve future-attempt time, but no executor enforces it.
- **FACT:** consumer service clients currently use 150-second outer timeouts.

**Recommended decision**

Canonical categories:

- `POLICY_PRIVACY_DENIED`, `CAPABILITY_UNAVAILABLE`, `REQUEST_INVALID`,
  `AUTHENTICATION`, `RATE_LIMIT`, `TRANSPORT`, `PROVIDER_5XX`,
  `SCHEMA_CONTRACT`, `DEADLINE_EXHAUSTED`, and `UNKNOWN_TERMINAL`;
- provider adapters map SDK/HTTP errors explicitly; class-name matching is not a
  canonical production classifier;
- retry/fallback eligibility is separate metadata, not implied only by category;
  policy/auth/request/schema errors are terminal by default.

Deadline semantics:

- caller establishes one monotonic end-to-end deadline at AI Core boundary;
- service handling, attempt timeout, backoff, provider fallback, validation, and
  response overhead all consume same budget;
- each attempt receives at most remaining budget minus declared reserve;
- no retry/fallback begins without minimum safe budget;
- consumer durable retry starts a new bounded request and does not extend an
  existing deadline;
- any outer HTTP timeout must exceed the accepted server deadline by only a
  documented bounded transport margin.

**Alternatives**

1. Keep PR #5 taxonomy unchanged.
2. Let each adapter expose native errors.
3. Give every attempt its full configured timeout.
4. Reuse one deadline across durable job retries.

**Consequences of recommended choice**

- Stable consumer behavior across SDKs and transports.
- Deadline cannot grow with retry/fallback depth.
- Requires explicit adapter mappings and later integration tests.

**Consequences of alternatives**

- Native/heuristic errors create inconsistent retry behavior.
- Per-attempt full timeouts exceed caller SLA.
- Cross-job deadline reuse confuses durable workflow lifecycle.

**What remains deferred**

SDK adapters, HTTP status mapping details, retry delays, transport margin value,
executor enforcement, metrics, and consumer SLA migration.

**Effect on PR #3 / #4 / #5**

- PR #3/#4: no direct runtime approval.
- PR #5: pure budget math is a candidate; taxonomy/classifier needs revision;
  executor remains deferred.

**What this unlocks**

Pure error/deadline contract tests and later bounded executor design.

**Required authority**

Operator and platform-control error/deadline/fallback approval.

**Status:** `OPEN`

---

## D6 — GPU boundary and AI Core HTTP service boundary

D6 contains two independent subdecisions. Approval of one never approves the
other, STT, a new provider identity, runtime implementation, or deployment.

### D6a — GPU trust and network boundary

**Question**

Is `gpu_ollama` inside an accepted trusted boundary, and what evidence is needed
before sensitive data or automatic routes may use it?

**Why it matters**

Private-overlay reachability does not prove machine ownership, ingress policy,
credential protection, or payload handling.

**Current evidence**

- **FACT:** accepted catalog labels `gpu_ollama` `UNKNOWN_BOUNDARY`.
- **FACT:** endpoint normalization/reachability were confirmed.
- **FACT:** GPU vision returned HTTP 503 during runtime validation.
- **INFERENCE:** 503 is `FAILED_INCONCLUSIVE`, not runtime capability proof.

**Recommended decision**

Retain `UNKNOWN_BOUNDARY` and deny sensitive raw data until platform-control
records host ownership, network path, ingress/auth, logging, retention, operator,
probe, and rollback evidence. Do not raise any GPU model evidence level from
normalization, reachability, or HTTP 503.

**Alternatives**

1. Treat private-overlay reachability as `PRIVATE_TRUSTED_INFRA`.
2. Treat the GPU host as external/untrusted permanently.

**Consequences of recommended choice**

Safe default; GPU use for sensitive workloads waits for auditable boundary
evidence. Public/synthetic exploration still needs explicit D3/D4 policy.

**Consequences of alternatives**

- Option 1 silently upgrades trust without operational proof.
- Option 2 is safe but may permanently exclude legitimate private capacity.

**What remains deferred**

Infrastructure inspection, auth changes, live probes, deployment, model install,
runtime route, and `gpu_whisper` identity.

**Effect on PR #3 / #4 / #5**

- PR #3: keep unknown boundary/fail-closed raw policy only.
- PR #4: no GPU capability promotion or Whisper identity acceptance.
- PR #5: unknown health/boundary cannot route by default.

**What this unlocks**

After separate infrastructure evidence and approval: trusted-boundary policy
review. It does not unlock service/runtime.

**Required authority**

Operator, platform-control, infrastructure owner, and deployment lock for any
later infrastructure action.

**Status:** `OPEN`

### D6b — AI Core HTTP service ownership, auth, and deployment

**Question**

Should AI Core expose an internal HTTP service, and who owns client/server
contract, authentication, credentials, payload sanitation, and deployment?

**Why it matters**

Two consumers already assume HTTP clients, but clients alone do not establish a
canonical server or operational owner.

**Current evidence**

- **FACT:** E12 records two consumer-local v1 endpoint shapes and durable retry.
- **FACT:** no canonical AI Core server, auth contract, deployment artifact, or
  accepted service ADR exists.
- **FACT:** runtime implementation and deployment remain prohibited.
- **INFERENCE:** existing clients are requirements/evidence, not server authority.

**Recommended decision**

Do not include HTTP service in foundation. Authorize a later service-contract
design package only, with proposed ownership:

- AI Core owns bounded inference API, request validation, policy enforcement,
  provider-call execution result, and metadata-only tracing;
- consumers own durable jobs, media storage/normalization, domain sanitation,
  idempotency, workflow retry, and result persistence;
- service validates internal authentication; deployment owner provisions and
  rotates service/provider credentials;
- platform-control owns deployment topology and lock-governed activation;
- existing transcription/image-description endpoints are inputs to design and
  may be revised; they are not adopted as-is by this decision.

**Alternatives**

1. Keep AI Core library-only; consumers own provider runtime.
2. Adopt both existing client contracts as canonical server API immediately.
3. Put durable queues/media lifecycle inside AI Core service.

**Consequences of recommended choice**

- Foundation stays small; service questions get independent review.
- Consumer-owned durable semantics remain intact.
- Requires later contract, threat-model, auth, deployment, and compatibility
  work before runtime.

**Consequences of alternatives**

- Library-only preserves duplicated runtime/fallback across services.
- Immediate client-contract adoption freezes unreviewed auth and media shapes.
- Central durable queues couple AI Core to product workflow/persistence.

**What remains deferred**

Service acceptance, endpoint schema, auth mechanism, credential lifecycle,
payload limits, sanitation evidence, SLOs, deployment, transport/executor, STT,
vision, and consumer migration.

**Effect on PR #3 / #4 / #5**

No current PR gains service/runtime authorization. Their pure contracts remain
subject to D1-D5.

**What this unlocks**

Only a separate AI Core service ADR/design work package. It does not accept STT,
new identities, GPU trust, runtime, or deployment.

**Required authority**

Operator and platform-control architecture approval; infrastructure owner and
deployment lock for later deployment action; consumer owners for migrations.

**Status:** `OPEN`

---

## 4. Operator choice sheet

All boxes intentionally unchecked. Checking this copy does not replace the
required platform-control decision record.

- [ ] **D1:** authorize additive, submodule-only, dependency-light foundation
  after pointer reconciliation; root API unchanged.
- [ ] **D2:** confirm all-form/all-boundary `SECRET` denial and fail-closed
  missing egress authorization.
- [ ] **D3:** keep four accepted IDs; adopt evidence levels; defer new IDs and
  `STT_SEGMENTS`; require runtime-observed evidence for production routing.
- [ ] **D4:** preserve explicit request order; exclude `UNKNOWN` by default;
  future AI Core execution layer owns provider-call retry/fallback, consumer
  owns durable retry.
- [ ] **D5:** accept canonical policy-to-deadline taxonomy and one monotonic
  end-to-end request deadline.
- [ ] **D6a:** retain GPU unknown boundary until operational evidence and
  separate approval.
- [ ] **D6b:** keep service outside foundation; authorize only a later service
  contract design if desired.

## 5. Recommended approval order

1. Reconcile factual main pointer, then decide D1.
2. Decide D2 before any provider/routing merge.
3. Decide D3 before capability registry or alias expansion.
4. Decide D4 and D5 before route planner/executor work.
5. Decide D6a and D6b independently; neither blocks review of a pure foundation.

No decision above is accepted by this document.
