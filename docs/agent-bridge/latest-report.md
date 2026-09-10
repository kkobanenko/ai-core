# Latest agent report

**Work package:** S0 AI Core governance recording and pointer reconciliation
**Status:** COMPLETE / PUBLISHED FOR REVIEW / WAIT
**Date:** 2026-09-10

## Outcome

Accepted operator policy D1-D6 is encoded as a proposed platform-control
governance change. The change is published as draft PR #294 and CI is green.
It is not authoritative on `platform-control/main` until separately reviewed
and merged.

No runtime, service, transport, executor, provider call, consumer, deployment,
release, tag, AI Core main, or AI Core PR #3-#5 change was made.

## Git and review state

### platform-control

- Branch: `governance/ai-core-s0-20260910`
- Base: `6445a2ed8614ae0bb663b92413ebf04f3fbc1d99`
- Head: `0fd1354ee471b40165a50d016a6a28970db8443b`
- Draft PR: https://github.com/kkobanenko/platform-control/pull/294
- PR state: OPEN / DRAFT / MERGEABLE
- CI: GREEN, Infrastructure CI run `34486623033`
- Merge performed: no

### ai-core

- Bridge branch: `test/ai-core-compatibility-characterization-20260909`
- Bridge starting head: `fdb4f1bb4401bd5bf09ae8a2a7aa9a4370f93224`
- Production main: `7569441c18362cfd15524ad73f56f7f35580c86f`
- Production main changed: no
- Bridge delivery head: resolve with `git rev-parse HEAD`; final response records
  exact pushed SHA to avoid recursive self-reference.

Fresh read-only GitHub verification before publication:

| Item | State | Exact head |
|---|---|---|
| AI Core PR #3 | OPEN / DRAFT / no approval | `4e26d67b825194e489a6a8b553c2a53dfea2a81f` |
| AI Core PR #4 | OPEN / DRAFT / no approval | `1b2569a612968a3ac5099dea955cfccdcb191d52` |
| AI Core PR #5 | OPEN / DRAFT / no approval | `25c269bb93dd37bd9b1556051972f5e1e60b34ad` |
| Platform issue #291 | OPEN / no comments or labels | n/a |
| Platform issue #292 | OPEN / no comments or labels | n/a |
| Platform issue #293 | OPEN / no comments or labels | n/a |

## platform-control files changed

1. `config/compatibility.yaml`
2. `coordination/current-initiative.yaml`
3. `coordination/initiatives.yaml`
4. `coordination/initiatives/ai-core-v0.3-design/initiative.yaml`
5. `coordination/orchestrator-state.yaml`
6. `coordination/initiatives/ai-core-v0.3-design/evidence/operator-decision-ai-core-foundation-governance.yaml`
7. `docs/adr/ADR-022-ai-core-foundation-governance.md`
8. `docs/decisions/2026-09-10-accept-ai-core-foundation-governance.md`
9. `tests/test_ai_core_s0_governance_decision.py`

Changed paths are limited to governance/configuration, coordination, docs, and
tests. `config/projects.yaml`, runtime source, infrastructure, deployment, and
consumer repositories are untouched.

## Pointer reconciliation

The intended observed pointer in `config/compatibility.yaml` changed from stale
`83acc5304bd87451a0dc96d7a3b0ca663ec6769f` to freshly verified factual
`ai-core/main` `7569441c18362cfd15524ad73f56f7f35580c86f`.

The dedicated initiative and three canonical indexes now agree on:

- `kind: foundation_only`;
- `authorization.status: FOUNDATION_ONLY`;
- `foundation_contracts_authorized: true`;
- `foundation_work_package_start_authorized: false`;
- runtime/service/consumer implementation authorization: false;
- evidence path and exact AI Core main SHA.

The legacy broad `ai_core_v0_3_implementation_authorized` flag remains false so
it cannot be read as runtime authorization.

## Encoded decisions

- **D1:** additive dependency-light foundation only; existing nine-symbol root
  API unchanged; S1 start still separately blocked.
- **D2:** `SECRET` in RAW/SANITIZED/SURROGATED form at every boundary yields
  zero routes and zero provider attempts before routing; missing egress fails
  closed.
- **D3:** exact accepted provider IDs remain `vm100_local_ollama`,
  `gpu_ollama`, `ollama_cloud`, `mistral_external`; new IDs and
  `STT_SEGMENTS` remain deferred. Evidence is attached to exact provider,
  model, capability, and boundary. GPU vision 503 is `FAILED_INCONCLUSIVE` and
  non-promoting; Ollama normalization/reachability is reachability-only.
- **D4:** AI Core is target canonical routing owner; caller physical order is
  migration-compatibility-only; hidden catalog/lexical priority is forbidden;
  UNKNOWN health fails closed for normal production. Provider-call retry and
  provider fallback may belong to one future AI Core execution layer; durable
  workflow retry remains consumer-owned.
- **D5:** one monotonic end-to-end request deadline and normalized semantic
  error families are required; exact enum, counts, backoff, jitter, and circuit
  breaker remain deferred.
- **D6a:** `gpu_ollama` remains `UNKNOWN_BOUNDARY`; no trust or capability
  promotion and no sensitive RAW traffic.
- **D6b:** centralized HTTP service is a desired later target outside the
  foundation; separate ADR/design authorization required; no STT, identity,
  runtime, or deployment implication.

## Validation

- TDD cycles: expected RED failures observed before evidence, pointer,
  D2-D6, ADR/decision, S1-start, timestamp, exact-SHA, and publication records.
- `pytest -q tests/test_ai_core_s0_governance_decision.py`: **5 passed**.
- `PLATFORM_CONTROL_VALIDATE_MODE=control_plane ... validate_control.py`:
  **PASS**, one known workspace path-alias warning.
- Full local platform-control pytest: **1789 passed, 229 skipped, 3 failed**.
  The three failures are the pre-existing strict local `/home` versus `/mnt`
  exact-workspace allowlist mismatch; baseline was **1784 passed, 229 skipped,
  3 failed**. S0 added five passing tests and no new failure.
- `git diff --check`: PASS.
- Draft PR first CI run `34485931358`: pytest and validator passed; structure
  gate rejected missing PR-body `Merge gate` section.
- PR body corrected with an unchecked draft merge checklist; no gate weakened.
- Exact-head CI run `34486623033`: **GREEN**, including pytest, validator,
  merge-gate structure, compose checks, shell/systemd checks, secret scan,
  Docker builds, and startup smoke.

## Risks and blockers

- Draft PR #294 is proposed governance only; platform-control main still lacks
  the record.
- External architecture/governance review is pending.
- Explicit operator merge authorization is absent; merge remains forbidden.
- S1 work-package start is explicitly false.
- Runtime, service, transports, executor, consumers, deployment, release, and
  tags remain unauthorized.
- GPU boundary remains unknown; infrastructure evidence package is absent.
- Service contract/auth/deployment boundary needs a separate later ADR.
- Exact error enum and retry parameters remain intentionally deferred.
- Issues #291-#293 remain review evidence, not approval.
- Local strict-path validator mismatch remains an environmental baseline issue;
  hosted control-plane CI is green.

## Rollback

- Before merge: close draft PR #294 and delete
  `governance/ai-core-s0-20260910` if governance proposal is rejected.
- After a separately authorized merge: revert platform-control commits
  `0fd1354ee471b40165a50d016a6a28970db8443b` and its parent S0 commit.
- AI Core bridge rollback: revert the bridge documentation commit.
- No runtime, consumer, deployment, release, or tag rollback is required.

## Next recommended work package

First: external review of draft platform-control PR #294. If accepted, obtain
explicit merge authorization and merge through platform-control governance.

Only after that merge, request separate explicit authorization for
`S1_foundation_contracts`: dependency-light identity, capability/evidence,
privacy/egress, and pure contract types/tests; unchanged root API; no runtime,
service, transports, executor, or consumer migration.

Current bridge state: **WAIT**.
