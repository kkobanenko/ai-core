# AI Core Governance Decision Support Design

**Date:** 2026-09-09
**Branch:** `test/ai-core-compatibility-characterization-20260909`
**Package type:** governance decision support, documentation, read-only analysis

## 1. Goal

Give operator and platform-control reviewers small, evidence-backed decision set
needed before any AI Core runtime work. Package recommends outcomes but never
records recommendation as approved decision.

Each decision packet uses fixed shape:

`question -> recommended option -> alternatives -> consequences -> unlocked work -> evidence -> decision authority -> OPEN status`

## 2. Safety boundary

Allowed work:

- read current AI Core, platform-control, PR #3-#5, and pinned consumer evidence;
- refresh Git and GitHub facts read-only;
- write coordination and documentation artifacts on current branch;
- commit and push those documentation artifacts to current branch.

Forbidden work:

- no governance decision acceptance or `pending_decision` resolution;
- no write to platform-control, consumers, PR branches, or PR metadata;
- no runtime or production change under `src/ai_core/**`;
- no rebase, rewrite, split, merge, release, tag, deployment, transport,
  executor, service, provider identity, or capability expansion.

New evidence may change a recommendation. It may not expand package scope.

## 3. Recommended document model

Use one authoritative governance report with six grouped decision packets and
one PR decomposition plan. This keeps review small while preserving independent
approval boundaries. Agent bridge contains summary and restart instruction, not
a second source of truth.

Planned artifacts:

- `docs/governance/2026-09-09-ai-core-decision-packets.md`;
- `docs/governance/2026-09-09-ai-core-pr-decomposition-plan.md`;
- updated `docs/agent-bridge/latest-report.md`;
- archived bridge report and exact next prompt under `docs/agent-bridge/**`.

## 4. Decision packet groups

### D1. Baseline and governance observed state

Confirm factual AI Core `main` SHA, explain compatibility-pointer drift, and
identify authority and prerequisite for pointer reconciliation. Recommendation
must not mutate platform-control.

### D2. Privacy and explicit egress

Decide all-form/all-boundary `SECRET` handling and default when request-level
egress authorization is absent. Recommended posture: deny before alias
resolution and route construction; missing authorization fails closed.

### D3. Provider identities, evidence, and capabilities

Separate accepted four-provider catalog from proposed identities. Define
evidence levels without presenting configuration or reachability as runtime
capability proof. Keep `STT_SEGMENTS` outside accepted set until separately
approved with model, privacy, ownership, and service evidence.

### D4. Routing, health, order, and fallback ownership

Define route-order authority, `UNKNOWN` health eligibility, deterministic
exhaustion, and retry ownership. Treat three mechanisms independently:

- provider-call retry repeats one provider call;
- provider fallback selects another eligible provider;
- durable job/workflow retry reruns consumer workflow state.

Recommended posture: caller supplies an explicit policy-constrained candidate
set; unknown or missing safety inputs do not silently enable egress; one future
AI Core execution layer may own provider-call retry and provider fallback
orchestration, while durable job/workflow retry remains consumer-owned. No
single retry contract combines all three mechanisms.

### D5. Error taxonomy and shared deadline

Define canonical error classes and one end-to-end deadline covering attempt
timeout, retry delay, and fallback. Keep pure deadline arithmetic separable from
network execution.

### D6. GPU and service ownership boundary

Keep one compact packet with two independently approved subdecisions:

- **D6a:** GPU trust and network boundary;
- **D6b:** AI Core HTTP service ownership, authentication, and deployment
  boundary.

D6a approval does not authorize service/runtime work. D6b approval does not
accept STT, new provider identities, or GPU trust. Endpoint normalization and
reachability are confirmed. GPU vision HTTP 503 is a failed/inconclusive
runtime-validation attempt, not runtime capability evidence, and cannot raise
the model evidence level.

All six packets remain `OPEN` until platform-control or named decision authority
records approval outside this package.

## 5. PR decomposition design

Plan only; do not change PRs.

- **PR #3:** isolate dependency-light/root-compatible catalog and policy
  primitives; redesign transformed `SECRET` behavior; separate disputed policy
  from mergeable compatibility foundations.
- **PR #4:** isolate alias resolution and evidence representation for accepted
  identities; move new identities and `STT_SEGMENTS` into later governed units.
- **PR #5:** isolate pure deadline arithmetic and corrected planning contracts;
  gate health, order, egress, taxonomy, and fallback semantics on decisions;
  defer executor and transports.

For every proposed slice, plan records base dependency, retained files/symbols,
required decision IDs, validation, rollback, and explicit exclusions. It does
not authorize any history rewrite or branch operation.

## 6. Evidence method

Evidence hierarchy:

1. current remote Git/GitHub state and immutable SHAs;
2. platform-control tracked policy and issue state;
3. AI Core source/tests at pinned commits;
4. consumer source/config/tests at pinned commits;
5. live probe result, labelled by exact strength: capability-confirmed,
   reachability-only, or failed/inconclusive;
6. PR descriptions or comments as claims, never approval by themselves.

Every recommendation cites evidence and distinguishes observed fact, inference,
and proposed policy.

## 7. Validation

Before delivery:

- verify PR #3-#5 heads, bases, draft state, checks, and reviews;
- verify platform-control issues #291-#293 state and absence/presence of approval;
- verify factual AI Core main and recorded platform-control pointer;
- compare planned slices against pinned diffs;
- run existing full AI Core suite, consumer fixture verifier, changed-path guard,
  and `git diff --check`;
- confirm no production, consumer, platform-control, PR, tag, release, or
  deployment mutation;
- scan final docs for placeholders and contradictory decision status.

## 8. Completion and handoff

Package complete when operator receives six OPEN packets plus executable review
sequence and PR decomposition plan. Handoff records branch, package base SHA,
final remote SHA, changed documents, checks, risks, blockers, rollback, and next
authorized action.

`docs/agent-bridge/latest-report.md` points to authoritative artifacts. Final
`next-prompt.md` tells next agent to wait for operator/platform-control decisions
and forbids implementation, merge, release, and deployment without new scope.

Rollback: revert or delete documentation-only branch commits. Production main,
consumers, infrastructure, and existing PRs remain unchanged.
