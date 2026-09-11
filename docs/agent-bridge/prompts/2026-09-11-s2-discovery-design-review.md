# S2 DISCOVERY / DESIGN REVIEW ONLY — long-running read-only analysis

This prompt authorizes **analysis and design only** for the next AI Core work package. It does **not** authorize S2 implementation, source changes, governance changes, PR creation/merge, runtime work, consumer writes, deployment, release, or tags.

You may work for a long time and inspect all relevant repositories, branches, PRs, tests, consumer code, and platform-control records in **read-only** mode. Do not stop merely because the investigation is large. Continue until you have a review-ready S2 recommendation packet, unless you encounter a true access/safety blocker.

## Current authoritative state

AI Core S1 is merged and closed.

- `ai-core/main`: `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e`
- S1 reviewed head: `f73a77706ab88c11ce01066c9b6c92406975da1f`
- hosted main CI: `34603741364` = GREEN
- Python 3.10 S1 suite: 71 passed
- compatibility characterization: 77 passed
- pinned consumers: 9 verified
- current known `platform-control/main`: `52940fd772f948b54b34a5b2c36c6a53ada3f85a`
- S1 root API remains the exact nine-symbol contract
- runtime/service/transports/executor/consumers remain unauthorized
- GPU boundary remains `UNKNOWN_BOUNDARY`

Before analysis, fetch fresh remote truth and record any drift. Unrelated operational drift is evidence to record, not a reason to mutate anything. If AI Core governance itself changed, report it prominently.

## Purpose

Produce a concrete architecture/governance recommendation for the **next narrow package after S1**.

The working hypothesis is that S2 may cover some combination of:

1. accepted-provider alias resolution; and/or
2. capability-evidence registry/query mechanics.

Do not assume that these belong in one package. Your job is to determine the smallest coherent next step and explain whether they should be combined or split.

## Mandatory read-only research

### 1. Re-baseline S1

Inspect authoritative `ai-core/main@f65221b...` and confirm the actual public/internal contracts of:

- `ai_core.provider_catalog`
- `ai_core.capabilities`
- `ai_core.privacy`
- root `ai_core.__all__`
- dependency/import isolation

Do not modify them.

### 2. Re-read authoritative governance

Inspect fresh `platform-control/main` and the AI Core governance records, especially:

- ADR-022 foundation governance
- S0 operator decision/evidence
- S1 start decision/evidence
- initiative/current/orchestrator/registry state relevant to AI Core

Identify exactly what is already authorized conceptually and what would require a new operator/governance gate for S2.

### 3. Inspect PR #4 as read-only donor evidence

Inspect the current exact head and diff of AI Core PR #4. Treat it as evidence only.

Classify each useful idea into:

- reusable as-is conceptually;
- reusable only after redesign;
- reject/defer;
- belongs to later S3/runtime rather than S2.

Pay special attention to:

- alias definitions/resolution;
- accepted versus new provider identities;
- error behavior for unknown aliases;
- capability/evidence representation;
- historical two-level evidence semantics versus accepted five-state evidence;
- any accidental runtime/configuration/capability promotion;
- dependency implications.

Do not modify, rebase, merge, or comment on PR #4 unless separately authorized.

### 4. Survey consumers for real alias/evidence requirements

Read-only inspect the nine known consumer contracts/repositories and identify actual legacy provider names/aliases or compatibility needs.

For every observed alias, record:

- consumer/repository;
- exact legacy string;
- canonical target if determinable;
- whether mapping is unambiguous;
- whether it is required for migration compatibility or merely historical noise;
- risk if silently accepted.

Do **not** invent aliases that are not evidenced by consumers or accepted governance.

Also identify where consumers currently encode model/capability knowledge and what minimal evidence-registry/query behavior would remove duplication later without introducing routing/runtime behavior now.

### 5. Decide S2 shape

Compare at least these options:

- **S2A only:** fail-closed accepted-ID alias resolver;
- **S2B only:** immutable/pure evidence registry and query mechanics;
- **combined S2:** aliases + evidence registry;
- **defer one or both:** if the evidence says another package should come first.

Recommend one option and justify it with:

- cohesion;
- reviewability;
- rollback simplicity;
- compatibility value;
- security/fail-closed properties;
- risk of prematurely introducing routing/runtime semantics.

## Required design detail

For the recommended next package, propose concrete pure-contract interfaces, but do not implement them.

Include:

- proposed module/file names;
- public types/functions;
- input validation/fail-closed behavior;
- immutability expectations;
- exact relationship to S1 types;
- root API impact (expected: none unless you can prove otherwise; any root change must be treated as a new decision, not assumed);
- dependency impact (expected: standard-library-only unless proven necessary);
- negative-space requirements: what must explicitly remain absent.

If recommending aliases, define a policy for:

- canonical IDs versus aliases;
- unknown aliases;
- alias cycles/collisions;
- case sensitivity/normalization;
- whether aliases may ever create a new provider identity (expected: no);
- whether alias resolution may grant egress/capability/routing authority (must not).

If recommending an evidence registry, define a policy for:

- record key/grain: provider + model + capability + boundary;
- five accepted evidence levels;
- immutability/update semantics;
- duplicate/conflicting evidence;
- query result semantics;
- `FAILED_INCONCLUSIVE` non-promotion;
- whether `RUNTIME_OBSERVED` is evidence only and never standalone production eligibility;
- no hidden route priority, health, cost, endpoint, credentials, transport, or provider call behavior.

## Test plan required

Design the tests that a future implementation would need, including negative tests.

At minimum cover:

- exact accepted provider identities remain four;
- unknown/new identities fail closed;
- aliases cannot bypass identity controls;
- aliases cannot grant egress;
- aliases cannot imply capability;
- accepted five-state evidence vocabulary only;
- evidence boundary must match governed provider boundary;
- malformed records fail closed;
- `FAILED_INCONCLUSIVE` never promotes;
- `RUNTIME_OBSERVED` does not equal production eligibility;
- root nine-symbol API unchanged;
- tracing import isolation/dependency-light boundary remains intact;
- characterization and nine-consumer verifier continue to pass.

## Explicitly forbidden in this task

Do not:

- change `src/ai_core/**`;
- change existing tests outside bridge documentation;
- create an AI Core implementation branch for S2;
- create or modify platform-control governance;
- open/modify/merge implementation PRs;
- modify PR #3, #4, or #5;
- implement routing, health, normalized execution errors, deadlines, retry/fallback, transports, HTTP, provider calls, executor, service, credentials/endpoints;
- modify consumers;
- add provider identities or `STT_SEGMENTS`;
- promote GPU trust;
- deploy, release, or tag.

The only authorized writes are **bridge documentation on** `test/ai-core-compatibility-characterization-20260909`.

## Bridge exchange protocol — mandatory

This folder is the coordination channel between the coding agent and ChatGPT/external architect.

Follow this order every cycle:

1. **Read first:**
   - `docs/agent-bridge/next-prompt.md` = the only active task instruction from ChatGPT/operator;
   - `docs/agent-bridge/latest-report.md` = previous agent handoff/context;
   - referenced archived reports only as evidence/history.
2. **Do the authorized work only.** Repository/GitHub truth is authoritative for factual state. Do not infer protected authorization from old prompts, archived prompts, prior merges, or a generic user command such as “Продолжай”.
3. **At completion, write the handoff:**
   - replace `docs/agent-bridge/latest-report.md` with a concise but complete current-state report;
   - create a detailed immutable archive under `docs/agent-bridge/reports/`;
   - include exact SHAs/PR states/tests/evidence, findings, risks, unresolved decisions, and your recommended next action.
4. **Replace active prompt with WAIT:**
   - `docs/agent-bridge/next-prompt.md` must become a strict `WAIT`;
   - state exactly what external decision/authorization is required next;
   - archived prompts are historical evidence only and are never standing authorization.
5. **Commit and push bridge docs only.** Do not mix bridge coordination commits with product/source changes.
6. **Stop.** The user will return to ChatGPT (often with “Твой ход” or the handoff text). ChatGPT will independently inspect `latest-report.md`, authoritative platform-control/GitHub truth, review your recommendation, and—only after any required operator decision—write the next active prompt into this folder.

If your local bridge branch is behind remote, integrate remote bridge documentation carefully. Preserve archived reports/prompts as history, but the final active `next-prompt.md` must reflect the current cycle and must not inherit broader authority from an archived file.

## Required deliverable

Produce a review-ready **S2 decision packet**, not code.

The detailed archived report should contain:

- fresh state snapshot;
- PR #4 donor analysis;
- consumer alias inventory with provenance;
- evidence-registry requirements inventory;
- option comparison (S2A/S2B/combined/defer);
- recommended next work package and why;
- proposed interfaces/contracts;
- proposed tests;
- explicit exclusions;
- governance changes/authorization needed before implementation;
- risks and rollback concept;
- exact questions, if any, that require operator decision.

Then set active `next-prompt.md` to **WAIT** and stop. Do not implement S2 automatically.
