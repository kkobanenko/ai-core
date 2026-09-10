# Latest agent report

**Work package:** S1 foundation-contracts control-plane start gate
**Status:** DRAFT PUBLISHED / EXACT-HEAD CI GREEN / WAIT
**Report date:** 2026-09-11

## Outcome

Authoritative `platform-control/main` still had
`foundation_work_package_start_authorized: false`, so the operator-approved
control-plane gate was required before any AI Core source work.

A minimal governance/docs/tests-only proposal was created on a fresh
platform-control worktree, pushed, and published as draft PR #295. Hosted CI is
green on the exact head. The PR was not merged, and S1 implementation was not
started.

## Exact Git and PR state

### platform-control

- Authoritative remote `main`: `35a922ceacb51ff2e8e8ccacc00291fbd2155b52`.
- Fresh branch: `governance/ai-core-s1-start-20260911`.
- Branch base: `35a922ceacb51ff2e8e8ccacc00291fbd2155b52`.
- Branch head: `44d30f1a81fe7736c83a6f49ce7fde5c91412b08`.
- Draft PR: https://github.com/kkobanenko/platform-control/pull/295
- PR state: `OPEN`, `DRAFT`, `MERGEABLE`.
- Hosted Infrastructure CI run: `34532744201`, `SUCCESS` on exact head.
- The PR merge checklist remains unchecked.

Because PR #295 is not merged, authoritative main still has S1 start false.
The true value exists only in the review proposal.

### ai-core

- Production remote `main`: `7569441c18362cfd15524ad73f56f7f35580c86f`.
- Bridge branch: `test/ai-core-compatibility-characterization-20260909`.
- Bridge starting head: `2d7c61c62f9dd4319250813f313bf25cf0de67d6`.
- No AI Core source, test, packaging, or runtime file changed in this work
  package.

## Proposed S1 authorization boundary

PR #295 proposes only:

```yaml
authorization:
  status: FOUNDATION_ONLY
  authorized_work_package: S1_foundation_contracts
  foundation_contracts_authorized: true
  foundation_work_package_start_authorized: true
  runtime_implementation_authorized: false
  service_implementation_authorized: false
  provider_transports_authorized: false
  executor_authorized: false
  consumer_migration_authorized: false
  release_authorized: false
  tag_authorized: false
  deployment_authorized: false
```

The broad legacy flag remains
`ai_core_v0_3_implementation_authorized: false`. The accepted provider set is
still exactly:

- `vm100_local_ollama`;
- `gpu_ollama`;
- `ollama_cloud`;
- `mistral_external`.

The root API remains the exact existing nine symbols. `STT_SEGMENTS` and new
provider identities remain unauthorized. `gpu_ollama` remains
`UNKNOWN_BOUNDARY`. GPU endpoint normalization/reachability evidence is kept
separate from the HTTP 503 failed/inconclusive runtime-validation attempt; no
runtime capability was promoted.

## platform-control changed files

- `coordination/current-initiative.yaml`
- `coordination/initiatives.yaml`
- `coordination/initiatives/ai-core-v0.3-design/initiative.yaml`
- `coordination/initiatives/ai-core-v0.3-design/evidence/operator-decision-ai-core-s1-foundation-start.yaml`
- `coordination/orchestrator-state.yaml`
- `docs/decisions/2026-09-11-authorize-ai-core-s1-foundation-contracts.md`
- `tests/test_ai_core_s0_governance_decision.py`
- `tests/test_ai_core_s1_start_governance.py`

The S0 test update removes stale assertions that canonical coordination indexes
must permanently point to the historical S0 evidence. It continues to guard the
immutable S0 record and compatibility pointer; the new S1 test owns current
canonical-index assertions.

## Verification

- TDD RED: 3 expected failures before evidence/index/decision artifacts existed.
- Focused S1 plus historical S0 guards: **8 passed**.
- Control-plane validator: **PASS**, one known `/home` versus `/mnt` workspace
  alias warning.
- Full local pytest, workstation-strict mode: **1792 passed, 229 skipped, 3
  failed**. All three failures exactly match the pre-change baseline path-alias
  failures.
- Full local pytest with control-plane mode: **1794 passed, 229 skipped, 1
  failed**. The remaining test intentionally deletes that mode on a workstation
  and reproduces the same path-alias failure.
- `git diff --check`: **PASS**.
- Hosted exact-head Infrastructure CI `34532744201`: **GREEN**, including
  pytest, control validation, PR merge-gate structure, compose/shell/systemd
  checks, secret scan, Docker builds, and image startup smoke.

## Read-only immutability checks

- AI Core PR #3 remains `OPEN/DRAFT` at
  `4e26d67b825194e489a6a8b553c2a53dfea2a81f`.
- AI Core PR #4 remains `OPEN/DRAFT` at
  `1b2569a612968a3ac5099dea955cfccdcb191d52`.
- AI Core PR #5 remains `OPEN/DRAFT` at
  `25c269bb93dd37bd9b1556051972f5e1e60b34ad`.
- No PR #3-#5 branch, metadata, base, or history was changed.
- No consumer, infrastructure, deployment, release, or tag action occurred.

## Risks and blockers

- PR #295 is review evidence only; it is not authoritative until merged.
- PR #295 merge requires a new explicit operator authorization.
- AI Core S1 source work remains blocked while authoritative main says start
  false.
- A future AI Core S1 PR will require separate review and merge authorization.
- Runtime, service, transports, provider calls, retry/fallback executor,
  consumers, deployment, release, tags, new identities, and `STT_SEGMENTS`
  remain forbidden.
- GPU trust remains unknown; no infrastructure evidence package exists.
- Local strict validation retains the known `/home` versus `/mnt` alias issue;
  hosted CI is authoritative and green.

## Rollback

Before merge, rollback is to close draft PR #295 and delete/drop branch
`governance/ai-core-s1-start-20260911`; authoritative main requires no revert.

Bridge-only rollback is a normal revert of the documentation commit containing
this report. No runtime or consumer rollback is needed.

## Recommended next action

External architecture/governance review of exact head
`44d30f1a81fe7736c83a6f49ce7fde5c91412b08`. If accepted, provide a separate
explicit authorization to merge only unchanged PR #295 after rechecking exact
base/head and green CI. Then verify authoritative `platform-control/main`
before starting a fresh AI Core S1 branch.

Current bridge state: **WAIT**.
