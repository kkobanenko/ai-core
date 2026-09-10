# AI Core S0 governance recording handoff

**Status:** COMPLETE / PUBLISHED FOR REVIEW / WAIT
**Date:** 2026-09-10

Platform-control branch `governance/ai-core-s0-20260910` records the accepted
D1-D6 policy boundary and reconciles the stale AI Core main pointer. Base is
`6445a2ed8614ae0bb663b92413ebf04f3fbc1d99`; published head is
`0fd1354ee471b40165a50d016a6a28970db8443b`.

Review surface: draft platform-control PR
https://github.com/kkobanenko/platform-control/pull/294. Exact-head
Infrastructure CI run `34486623033` is green. The proposal is not yet
authoritative on `platform-control/main`; it was not merged.

## Delivered platform-control artifacts

- `config/compatibility.yaml`
- `coordination/current-initiative.yaml`
- `coordination/initiatives.yaml`
- `coordination/initiatives/ai-core-v0.3-design/initiative.yaml`
- `coordination/orchestrator-state.yaml`
- `coordination/initiatives/ai-core-v0.3-design/evidence/operator-decision-ai-core-foundation-governance.yaml`
- `docs/adr/ADR-022-ai-core-foundation-governance.md`
- `docs/decisions/2026-09-10-accept-ai-core-foundation-governance.md`
- `tests/test_ai_core_s0_governance_decision.py`

## Decision boundary

Machine evidence records `FOUNDATION_ONLY`, but
`foundation_work_package_start_authorized: false`. Runtime, service,
transports, executor, consumers, merge, release, tags, deployment, new provider
IDs, STT, and GPU trust promotion remain unauthorized.

D4 explicitly makes AI Core future canonical routing owner, limits caller
physical order to migration compatibility, and keeps provider-call retry,
provider fallback, and consumer durable retry mechanically separate. D5
requires normalized semantic families and one monotonic end-to-end deadline
without freezing exact enum names. GPU vision HTTP 503 remains
failed/inconclusive and does not promote capability evidence.

## Validation

- S0 governance tests: 5 passed.
- Control-plane validator: PASS with one known path-alias warning.
- Full local suite: 1789 passed, 229 skipped, 3 pre-existing strict-path
  failures; no new failures.
- `git diff --check`: PASS.
- Exact-head GitHub CI run `34486623033`: GREEN through tests, validator,
  merge-gate structure, secret scan, Docker builds, and startup smoke.

## Remaining blockers

- External architecture/governance review of PR #294.
- Separate explicit merge authorization.
- Governance proposal must reach platform-control main before it is
  authoritative.
- Separate explicit S1 authorization after merge.
- GPU infrastructure evidence and service-boundary ADR remain later packages.
- Issues #291-#293 remain OPEN review evidence, not approval.

## Rollback and next action

Rollback before merge: close PR #294 and delete its branch. No production
rollback exists because runtime and consumers were untouched.

Next action: review PR #294. If accepted, authorize its merge. Then authorize a
separate S1 pure-foundation package. Until then: **WAIT**.
