# S0 — record accepted AI Core governance decisions

The operator has reviewed the governance decision-support package and explicitly accepts the recommendations D1–D6 **with the two ChatGPT refinements below for D4 and D5**.

This prompt is explicit authorization for **S0 governance recording and pointer reconciliation only**.

It is **not** runtime implementation authorization.

## Read first

Read and use as evidence:

- `docs/agent-bridge/latest-report.md`;
- `docs/governance/2026-09-09-ai-core-decision-packets.md`;
- `docs/governance/2026-09-09-ai-core-pr-decomposition-plan.md`;
- `docs/reports/2026-09-09-ai-core-compatibility-characterization-report.md`;
- current `platform-control` governance files and repository instructions.

Before writing anything, freshly verify:

- `ai-core/main` factual SHA;
- `platform-control/main` factual SHA;
- current platform-control compatibility pointer;
- current initiative / ADR / decision schema and conventions;
- state of platform-control issues #291–#293;
- state and heads of ai-core PR #3–#5.

If any factual state has changed, preserve the operator decisions below but rebase the governance record on fresh evidence and report the drift.

---

# Operator decisions to record

All decisions below are now **operator-approved policy intent**. They become authoritative project governance only when encoded through the applicable platform-control governance path.

## D1 — additive foundation: ACCEPTED

Authorize a narrowly scoped AI Core canonical foundation with these boundaries:

- current nine-symbol root `ai_core.__all__` remains unchanged;
- tracing stays dependency-light;
- new contracts live in explicit submodules;
- foundation may contain dependency-light identity, capability/evidence, privacy/egress and pure contract types/tests;
- no provider SDK, HTTP client/server, transport, executor, provider call, consumer migration, deployment, release or tag is authorized by D1;
- platform-control observed pointer must be reconciled to freshly verified factual `ai-core/main` before any foundation merge authorization.

**Critical:** do not set a broad flag such as `ai_core_v0_3_implementation_authorized=true` if that flag semantically authorizes runtime/service/transports. Preserve the runtime prohibition. Use the existing governance schema if it supports a narrow foundation-only authorization; otherwise add the smallest explicit decision/scope representation consistent with platform-control conventions so that `FOUNDATION_CONTRACTS` can be allowed while runtime remains forbidden.

## D2 — SECRET and egress: ACCEPTED

Record the invariant:

`SECRET -> inference denied -> zero eligible routes -> zero provider attempts`

for all outbound forms:

- RAW;
- SANITIZED;
- SURROGATED;

and all network boundaries.

Additional accepted rules:

- denial occurs before alias resolution, transformation, capability filtering, health, ordering, retry or fallback;
- sanitization/surrogation does not silently reclassify SECRET;
- a non-secret request requires explicit upstream classification/policy evidence;
- missing request-level egress authorization fails closed for external or unknown-boundary routes;
- catalog membership alone never grants egress;
- provider fallback may use only candidates authorized for the exact request.

## D3 — provider identities and evidence: ACCEPTED

Canonical foundation provider IDs remain exactly:

- `vm100_local_ollama`;
- `gpu_ollama`;
- `ollama_cloud`;
- `mistral_external`.

Do not accept in this package:

- `gpu_whisper`;
- `openai_external`;
- `deepseek_external`;
- `STT_SEGMENTS`.

Record evidence semantics separating provider identity from `(model, capability, network boundary)` evidence.

Accepted evidence language:

- `CONFIGURED`;
- `UNIT_TESTED`;
- `INTEGRATION_TESTED`;
- `RUNTIME_OBSERVED`;
- `FAILED_INCONCLUSIVE` as a non-promoting outcome marker.

For normal automatic production routing, capability eligibility requires `RUNTIME_OBSERVED` evidence **plus** all relevant privacy/identity/health/governance gates. `INTEGRATION_TESTED` may support explicit shadow/non-production evaluation only by default.

Historical evidence remains narrow:

- Mistral OCR live success is exact-path runtime evidence only;
- Ollama normalization/reachability is reachability evidence only;
- GPU vision HTTP 503 is failed/inconclusive and does not promote capability.

## D4 — routing, health and retry ownership: ACCEPTED WITH OPERATOR REFINEMENT

Do **not** encode the decision packet's original long-term rule that caller-provided provider order is the canonical routing authority.

The accepted target is:

### Canonical routing ownership

- AI Core owns canonical route ordering and route selection policy in the target architecture;
- consumers/callers provide requirements and constraints, not normally a physical provider chain;
- caller inputs may include capability, privacy/data class, explicit egress permission, cost/latency/SLA constraints and a named routing-policy profile;
- AI Core combines those constraints with canonical registry/policy/evidence/health to produce a deterministic route;
- catalog priority or lexical ordering must never act as an undocumented hidden policy;
- an explicit caller-provided ordered candidate list may exist only as a **migration/compatibility mode** to preserve legacy behavior during strangler migration, and must not become the normative long-term routing contract.

### Health

- `UNKNOWN` provider/model health is ineligible for normal automatic production routing;
- bounded exploration may admit UNKNOWN only with explicit opt-in, non-secret policy-authorized payload and no automatic evidence promotion;
- provider health and model/capability evidence remain separate concepts.

### Three retry layers

Keep these mechanically distinct:

1. provider-call retry = same provider/model call, narrowly classified transient failure;
2. provider fallback = move to another already-authorized route candidate;
3. durable job/workflow retry = restart/resume product/domain workflow.

Target ownership:

- one future AI Core execution layer owns provider-call retry and provider fallback for one bounded inference request;
- nested provider fallback is forbidden;
- durable job/workflow retry remains consumer-owned;
- each durable retry starts a new bounded inference request with a new deadline.

Exact retry counts/backoff/jitter/circuit-breaker behavior remain deferred.

## D5 — errors and deadline: ACCEPTED IN PRINCIPLE WITH TAXONOMY REFINEMENT

Accept the principles:

- normalized AI Core errors;
- explicit retry/fallback eligibility metadata;
- one monotonic end-to-end deadline for each bounded inference request;
- service overhead, attempt timeout, backoff, provider fallback, validation and response overhead all consume that same budget;
- no retry/fallback starts without sufficient remaining budget;
- durable workflow retry begins a new bounded request and does not extend the old deadline.

Do **not** freeze the decision packet's proposed exact enum as the final canonical taxonomy in S0.

Governance must require that the future contract preserve machine-distinguishable causes at least across these semantic families:

- privacy rejection;
- egress rejection;
- no eligible route;
- unsupported capability;
- model unavailable;
- provider unavailable;
- authentication;
- rate limiting;
- transport failure;
- timeout/deadline exhaustion;
- malformed output;
- schema/contract mismatch;
- invalid request;
- unknown terminal failure.

The exact names and final enum belong to the later pure contract WP. The important governance decision is that these meanings must not be collapsed when they imply different retry/fallback/operator behavior.

## D6a — GPU trust boundary: ACCEPTED

Keep `gpu_ollama` as `UNKNOWN_BOUNDARY`.

Do not allow sensitive RAW traffic or automatic trust promotion until a separate infrastructure evidence package records at least host ownership, network path, ingress/auth, logging/retention, operator ownership, probe evidence and rollback.

Reachability or private-overlay access is not sufficient proof of trusted infrastructure.

This decision does not accept `gpu_whisper`, STT, vision capability, runtime or deployment.

## D6b — AI Core HTTP service boundary: ACCEPTED

Record the architecture direction:

- HTTP/service runtime stays **outside the minimal foundation**;
- a centralized AI Core service is a valid/desired later target for bounded inference, but requires a separate service-contract/ADR package before implementation;
- current transcription/image-description clients are requirements/evidence, not automatically canonical server APIs;
- future AI Core service may own bounded inference request validation, policy enforcement, provider execution result and metadata-only tracing;
- consumers retain durable jobs/queues, media/domain storage, business workflow state, domain prompts/schemas/validation, idempotency and durable retry;
- auth mechanism, credential lifecycle, endpoint schemas, payload limits, sanitation boundary, SLOs, deployment topology and activation remain deferred;
- D6b does not accept STT, new provider identities, GPU trust, runtime implementation or deployment.

---

# S0 implementation scope

Work primarily in `/home/kok4444/projects/platform-control` (or the actual current platform-control checkout if different).

## Allowed

- inspect platform-control governance conventions;
- create a fresh platform-control governance branch from current `main`;
- correct the stale observed `ai_core_main_sha` pointer to the freshly verified factual AI Core main SHA where that field is intended to reflect observed state;
- add/update the minimal governance decision records necessary to encode D1–D6 and the D4/D5 refinements above;
- preserve runtime/service/transports/consumer implementation prohibition while authorizing only the narrow foundation/contracts scope that D1 actually permits;
- update current initiative/compatibility/ADR/decision metadata only where required by the repository's canonical governance model;
- add tests/validation for governance schema if repository conventions require them;
- commit and push the platform-control governance branch;
- create a **DRAFT platform-control PR to `main`** as a review surface if platform-control workflow uses PR review. Do not merge it;
- reference issues #291–#293 in the governance record/PR body as review evidence, but do not treat their existence as approval.

## Forbidden

- no change to `ai-core/main`;
- no change to `src/ai_core/**`;
- no modification/rebase/rewrite of ai-core PR #3/#4/#5 branches or metadata;
- no consumer changes;
- no provider transports/executor/service/runtime implementation;
- no new provider IDs or STT acceptance;
- no GPU trust promotion;
- no release/tag/deployment;
- no merging to platform-control main unless the user separately authorizes merge after review;
- no broad implementation authorization that could be read as permitting runtime/service work.

---

# Governance-record quality requirements

The resulting platform-control record must make it mechanically difficult for a later agent to misread the decisions.

At minimum make explicit:

- `FOUNDATION_ONLY` / equivalent narrow authorization boundary;
- `RUNTIME_IMPLEMENTATION = NOT_AUTHORIZED`;
- `SERVICE_IMPLEMENTATION = NOT_AUTHORIZED`;
- `CONSUMER_MIGRATION = NOT_AUTHORIZED`;
- exact four accepted provider IDs;
- new IDs and STT remain pending/deferred;
- SECRET all-form zero-attempt invariant;
- missing egress authorization fails closed;
- AI Core is long-term canonical routing owner, while explicit caller order is migration-only compatibility behavior;
- UNKNOWN health fail-closed for normal production routing;
- provider retry/fallback ownership versus consumer durable retry;
- one end-to-end request deadline;
- normalized error semantics required, exact enum deferred;
- GPU boundary remains UNKNOWN;
- HTTP service is outside foundation and requires separate ADR/design authorization.

If platform-control's existing schema cannot express these cleanly, do not invent an ambiguous boolean. Add the smallest explicit decision document/field structure consistent with repository patterns and document why.

---

# Validation

Before handoff:

1. validate platform-control repository tests/schema/lint required by its normal workflow;
2. `git diff --check`;
3. prove the branch changes only governance/coordination/test paths appropriate to S0;
4. verify `ai-core/main` unchanged;
5. verify ai-core PR #3–#5 heads/metadata unchanged;
6. verify consumers unchanged;
7. verify runtime/service implementation is still explicitly forbidden after your governance edits;
8. re-read the final governance record looking specifically for contradictions between D4 original packet wording and the accepted D4 refinement;
9. re-read D5 to ensure an exact enum was not accidentally frozen;
10. confirm the stale main pointer is corrected or explain exactly why repository semantics prevent correction in this package.

Do not weaken a test or governance guard merely to make validation green.

---

# Handoff back through agent bridge

After the platform-control governance branch is pushed/review surface created:

Update the AI Core coordination bridge on branch:

`test/ai-core-compatibility-characterization-20260909`

with a new `docs/agent-bridge/latest-report.md` that records:

- platform-control branch;
- platform-control base/head;
- draft PR number if created;
- exact files changed;
- pointer reconciliation result;
- which D1–D6 decisions are now encoded in the proposed governance change;
- whether the governance change is only proposed/reviewable or actually authoritative on `platform-control/main`;
- all validation results;
- remaining blockers;
- exact next recommended WP.

Archive the report under `docs/agent-bridge/reports/`.

Set `docs/agent-bridge/next-prompt.md` back to WAIT after completion.

You may commit/push bridge documentation to the current AI Core characterization branch for handoff. Do not create or merge an AI Core PR as part of S0.

## Stop condition

Stop after governance records/pointer reconciliation are prepared and published for review.

Do **not** start S1 foundation implementation until ChatGPT/user reviews your S0 report and explicitly authorizes it.