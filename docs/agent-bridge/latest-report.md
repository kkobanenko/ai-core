# Latest agent report

**Work package:** S1 foundation contracts
**Status:** IMPLEMENTED / DRAFT PR / EXACT-HEAD CI GREEN / WAIT
**Report date:** 2026-09-11

## Outcome

The authoritative `S1_foundation_contracts` package was implemented on a fresh
AI Core branch from verified main. The result is a dependency-light contract
layer only: provider identities, capability evidence, privacy/egress, focused
tests, design/plan, and project handoff.

Draft AI Core PR #6 is published and green on its exact head. It was not
merged. Runtime, service, transports, provider calls, executor,
retry/fallback execution, consumers, infrastructure, deployment, release, and
tags were not changed.

## Exact governance and Git state

### platform-control

- Authoritative `main`:
  `c78b5e735d9b47e6550f2f6f7df084406c3ecfe0`
- Authoritative policy: `FOUNDATION_ONLY`
- Authorized package: `S1_foundation_contracts`
- `foundation_work_package_start_authorized: true`
- Broad `ai_core_v0_3_implementation_authorized: false`
- Runtime/service/transports/executor/consumers/release/tag/deployment: false

### ai-core

- Production `main`: `7569441c18362cfd15524ad73f56f7f35580c86f`
- Branch: `feat/ai-core-s1-foundation-contracts-20260911`
- Base: `7569441c18362cfd15524ad73f56f7f35580c86f`
- Head: `f73a77706ab88c11ce01066c9b6c92406975da1f`
- Draft PR: https://github.com/kkobanenko/ai-core/pull/6
- PR state: `OPEN`, `DRAFT`, `MERGEABLE`
- Exact-head Python 3.12 CI run `34572528885`: `SUCCESS`
- Review gate: hosted CI complete; external review and merge authorization open

The S1 worktree is outside the user's untracked project-local `.worktrees/`:
`/home/kok4444/projects/_coord_worktrees/ai-core-s1-foundation-contracts-20260911`.
The user's `.worktrees/` and `uv.lock` were not modified or deleted.

## Delivered source contracts

### `ai_core.provider_catalog`

- exactly four accepted provider IDs;
- immutable identity/boundary records and read-only catalog;
- explicit fail-closed unknown-ID error;
- `gpu_ollama` remains `UNKNOWN_BOUNDARY`;
- no endpoint, credential, backend, health, cost, latency, priority, model, or
  capability behavior.

### `ai_core.capabilities`

- pure capability vocabulary: text, structured JSON, vision image, OCR PDF;
- exact evidence levels: `CONFIGURED`, `UNIT_TESTED`, `INTEGRATION_TESTED`,
  `RUNTIME_OBSERVED`, `FAILED_INCONCLUSIVE`;
- immutable evidence subject `(provider, model, capability, boundary)`;
- fail-closed validation for unknown/invalid subject values and boundary drift;
- only `RUNTIME_OBSERVED` counts as a runtime observation, without implying
  routing or production eligibility;
- no concrete profiles and no `STT_SEGMENTS`.

### `ai_core.privacy`

- exact data-class and outbound-form vocabularies;
- all 3 forms × 3 boundaries for `SECRET` deny pre-routing;
- transformation cannot reclassify SECRET;
- missing request-level authorization denies external and unknown egress;
- authorization accepts only literal `True`;
- non-enum values fail closed;
- catalog membership cannot grant egress.

## Compatibility boundary

- Exact existing nine-symbol root `ai_core.__all__` is unchanged.
- Existing tracing/config/attributes/IO source is unchanged.
- New APIs require explicit submodule imports.
- Tracing import does not load foundation or provider dependencies.
- `pyproject.toml` is unchanged; no dependency/lock change.
- No aliases, routing, health, deadline, transport, SDK, service, or executor.

## Changed files

- `src/ai_core/provider_catalog.py`
- `src/ai_core/capabilities.py`
- `src/ai_core/privacy.py`
- `tests/test_s1_provider_catalog.py`
- `tests/test_s1_capability_evidence.py`
- `tests/test_s1_privacy_egress.py`
- `tests/test_s1_compatibility_boundary.py`
- `docs/superpowers/specs/2026-09-11-ai-core-s1-foundation-contracts-design.md`
- `docs/superpowers/plans/2026-09-11-ai-core-s1-foundation-contracts.md`
- `docs/handoffs/2026-09-11-ai-core-s1-foundation-contracts.md`

All are new files. No pre-existing AI Core file changed.

## PR #3 provenance

PR #3 head `4e26d67b...` was read-only donor evidence. No commit was
cherry-picked.

Reimplemented test-first:

- canonical constants;
- immutable identity records and fail-closed lookup;
- model-scoped capability vocabulary;
- data-class/outbound-form vocabulary;
- explicit submodule APIs.

Redesigned:

- behavioral provider profiles reduced to identity+boundary;
- extra boundary states aligned to authoritative vocabulary;
- concrete capability booleans/profiles replaced with evidence-only types;
- transformed SECRET eligibility replaced with all-form denial;
- catalog PII authority replaced by request-level authorization.

Excluded:

- endpoint/credential metadata and resolution;
- backend/health/cost/latency/priority;
- concrete model profiles;
- aliases;
- route/health/deadline/retry/fallback/runtime/service work.

## Verification evidence

- Baseline: **24 passed** on Python 3.10 using local `src`.
- Final Python 3.10 AI Core suite: **71 passed**.
- Hosted exact-head Python 3.12 CI `34572528885`: **GREEN**.
- Read-only compatibility characterization with S1 source: **77 passed**.
- Pinned workspace verifier: **9 consumer contracts verified**.
- Compile check: **PASS**.
- `git diff --check`: **PASS**.
- GitHub changed-path check: exactly ten S1 source/test/docs files.
- Dependency and existing-production-path audit: no changes.

TDD evidence includes module-not-found RED for each new source module, then
focused/full GREEN. Self-review found two runtime type-validation gaps:

- privacy invalid/truthy inputs: RED 6 failures, then 23 focused and 66 full
  passes;
- invalid capability-evidence subjects: RED 4 failures, then 15 focused and 71
  full passes.

The local environment emits an existing `pytest-asyncio` deprecation warning.
It was not hidden by changing dependencies/configuration.

## Read-only immutability checks

- AI Core main remains `7569441c...`.
- PR #3 remains `OPEN/DRAFT` at `4e26d67b...`.
- PR #4 remains `OPEN/DRAFT` at `1b2569a6...`.
- PR #5 remains `OPEN/DRAFT` at `25c269bb...`.
- Tags `v0.1.0`, `v0.2.0`, `v0.2.1`, and `v0.2.2` retain their prior tag and
  peeled SHAs.
- Consumer repositories were only read through pinned Git evidence; no write or
  execution occurred.
- No release, tag, deployment, or infrastructure action occurred.

## Risks and blockers

- PR #6 requires external architecture/governance review.
- Merge is forbidden without separate explicit operator authorization.
- These contracts do not execute or enforce provider calls; consumers retain
  current behavior until separately governed migration.
- Provider network boundaries are governance snapshots; GPU remains unknown.
- No concrete capability evidence is shipped, so no production route becomes
  eligible through S1.
- Aliases and downstream adoption are deferred.

## Rollback

Before merge, close draft PR #6 and drop branch/worktree
`feat/ai-core-s1-foundation-contracts-20260911`. Main, consumers, runtime,
deployment, releases, and tags need no rollback.

If later merged, use a separately reviewed revert; never rewrite main or tags.

## Recommended next action

Review exact PR #6 head `f73a7770...` against platform-control ADR-022 and the
S1 boundary. If accepted, issue a separate authorization that names PR #6,
exact base/head, and green CI. Do not authorize runtime or later S2/S3 work
implicitly.

Current bridge state: **WAIT**.
