# Handoff: AI Core transition baseline

## Scope

Completed the safe first work package only:

- current repository/governance baseline;
- read-only inventory of all top-level projects/directories and AI consumers;
- source-of-truth/ownership map;
- compatibility and existing-test audit;
- draft PR #3/#4/#5 assessment;
- blockers, risks, rollback, and next bounded work package.

No runtime, transport, retry/fallback executor, service, consumer,
infrastructure, deployment, provider-identity, release, tag, or `main` change
was made. `STT_SEGMENTS` was not accepted and no `pending_decision` was
resolved.

## Repository

`kkobanenko/ai-core`

## Branch

`docs/ai-core-transition-baseline-20260908`

## Base SHA

`7569441c18362cfd15524ad73f56f7f35580c86f`

## Head SHA

- Evidence/content commit before this handoff:
  `5026d9fb0dcdbeab8b10adc8243745ed4987b03c`.
- The delivery head is the commit containing this handoff. Because a commit
  cannot embed its own SHA, resolve it with `git rev-parse HEAD`; the exact
  value is also recorded in the delivery response.

Earlier planning commits on the same branch:

- `20ef495` — approved design/constraints;
- `168ca60` — documentation-only execution plan.

## Changed documents

- `docs/migration/current_state_baseline.md`
- `docs/architecture/cross_project_ai_inventory.md`
- `docs/architecture/source_of_truth_map.md`
- `docs/handoffs/2026-09-08-ai-core-transition-baseline.md`
- `docs/superpowers/specs/2026-09-08-ai-core-transition-baseline-design.md`
- `docs/superpowers/plans/2026-09-08-ai-core-transition-baseline.md`

All changes are Markdown. Runtime source, test source, dependency manifests,
consumer repositories, platform-control, tags, and releases are unchanged.

## Production baseline established

`ai-core main@7569441` is the production/default baseline and remains a
tracing/config/IO-policy package with an exact nine-symbol root API. `v0.2.0`,
`v0.2.1`, and `v0.2.2` are divergent historical provider lines. They are
evidence/compatibility anchors, not implicit successors to `main`.

Current consumers remain heterogeneous:

- Prozakupki is pinned to `v0.2.0` for its optional adapter and retains legacy
  execution as the production default;
- Zoom is pinned to `v0.1.0` and owns its provider loop;
- Clin-rec and KMO do not install ai-core and own local execution;
- Landing Sell and agent-lab use `v0.2.1` contracts;
- transcription and image-description services have version-1 AI-core HTTP
  clients in `origin/main`, default to `fake`, and have no matching server in
  current ai-core;
- Alpha main has a deterministic Tesseract OCR shadow and an accepted narrow
  boundary, but no ai-core/LLM runtime dependency was found.

## Checks performed

Fresh final verification on the documentation commit:

```text
PYTHONPATH=src python3.10 -m pytest -q
24 passed in 0.12s
```

One pre-existing pytest-asyncio deprecation warning reports an unset
`asyncio_default_fixture_loop_scope`. It does not fail the suite.

Additional checks:

- `git diff --check 7569441...HEAD` — passed;
- changed-file inspection — only the five planned baseline/design/plan
  Markdown files existed before adding this handoff;
- marker scan for `TBD`, `TODO`, false pending-decision resolution,
  `STT_SEGMENTS` acceptance, and merge-ready claims — all hits inspected and
  correctly state prohibition/unaccepted status;
- cited Prozakupki material paths — present;
- every allowlisted project — explicitly classified;
- every top-level workspace entry — classified as project, auxiliary checkout,
  artifact/data, or non-project file;
- primary checkout — still `main...origin/main` with only the pre-existing
  untracked `.worktrees/` and `uv.lock`; both existence checks passed.

The unsupported plain `python -m pytest -q` path used system Python 3.9 and
failed collection before the supported run. This was recorded as an
environment/setup mismatch, not hidden as a test failure.

## PR #3/#4/#5 disposition

### PR #3

Keep draft/blocked. The dependency-light, submodule-only, exact-root-preserving
foundation is directionally aligned and may be reconsidered after a real
platform-control review. Before acceptance it must block `SECRET` for every
outbound form, separate legacy provider hints from model routing truth, improve
evidence/compatibility tests, and remove any implication that implementation
was already authorized.

### PR #4

Keep draft/blocked and split. Alias/evidence machinery limited to the accepted
four provider identities may be reconsidered after governance and corrections.
`gpu_whisper`, `openai_external`, `deepseek_external`, and `STT_SEGMENTS` must
be deferred to separate governance/evidence work packages. Configuration-only
model entries must not be described as runtime-proven capabilities.

### PR #5

Keep draft/blocked. Dependency-light planning/health/deadline contracts may be
reconsidered after decisions on error taxonomy, `UNKNOWN` health, route-order
authority, explicit allowed egress, and the inherited SECRET policy. Transport
and retry/fallback execution remain later work.

No PR was retargeted, merged, closed, approved, or marked merge-ready.

## Governance blockers

1. Platform-control `origin/main@6445a2ed8614ae0bb663b92413ebf04f3fbc1d99`
   still marks `ai-core-v0.3-design` as RFC/backlog only with
   `ai_core_v0_3_implementation_authorized: false`, `auto_start: false`, and an
   explicit implementation prohibition.
2. Accepted ADR-001 is narrower than the transition plan's final centralized
   runtime/service target. A successor/updated accepted decision is required
   before that target is implemented.
3. The reviews cited by ai-core PRs #3/#4/#5 as platform-control #293/#291/#292
   were not resolvable; an observed platform-control PR list ended at #287.
   A later refresh failed due the sandbox proxy. Their review state is
   **absent/unverifiable**, not accepted.
4. The compatibility matrix accepts only four canonical provider identities.
   Proposed additional identities and `STT_SEGMENTS` remain pending.
5. `gpu_ollama` has an intentionally unresolved/unknown network boundary; raw
   sensitive data remains denied.
6. Service runtime ownership, service-to-service auth, credentials/deployment,
   payload sanitization ownership, route ordering, unknown-health behavior,
   explicit egress defaults, and canonical error vocabulary remain unresolved.
7. No provider/fallback/tracing/privacy implementation can proceed without the
   required platform-control review. Infrastructure work would additionally
   require a deployment lock.

## Risks

- A wholesale merge of the historical v0.2 line would break the v0.1 root API
  and introduce hard dependencies for tracing-only consumers.
- Nested retry/fallback can multiply attempts/timeouts because ownership is
  currently consumer-specific.
- Provider-level capability flags or config-only evidence can falsely
  authorize model/media behavior.
- Treating a generic alias such as `ollama` as canonical can select the wrong
  network/privacy boundary.
- PR #3's current SECRET rule permits sanitized/surrogated SECRET data where
  the accepted matrix says DROP/BLOCK for all providers by default.
- PR #5's default authorization and UNKNOWN-health behavior may route more
  broadly than a fail-closed request contract intends.
- Media clients can be mistaken for an available central service; enabling
  them against current ai-core would fail.
- Several inspected working checkouts are on feature branches or dirty. The
  inventory records their exact revision and does not claim they are deployed
  production state.

## Consumer impact

`NONE`.

No consumer file or execution switch changed. Existing OLD paths and rollback
switches remain intact.

## Rollback

Delete/drop branch `docs/ai-core-transition-baseline-20260908` (or revert its
documentation commits). No production rollback, consumer pin change, tag
movement, service restart, infrastructure action, or data recovery is needed.

The primary checkout's `.worktrees/` and `uv.lock` are user-owned and were not
modified or removed.

## Recommended next work package

After explicit user authorization, run one **compatibility-characterization
tests only** package on a new branch. It should:

1. snapshot all v0.1 root signatures and tracing semantics;
2. characterize immutable v0.2 behavior in isolated dependency environments;
3. add synthetic, configuration-only representability fixtures for
   Prozakupki, KMO, Zoom, Clin-rec, Landing Sell, and agent-lab;
4. prove dependency-light imports without LangChain/httpx/provider SDKs;
5. lock the accepted all-form SECRET DROP/BLOCK policy without introducing
   new identities, capabilities, routing runtime, transports, or services.

In parallel, but outside that ai-core test package, platform-control should
create real review records and decide whether the transition plan requires a
successor to ADR-001. Do not start PR #3 implementation reconciliation until
both the compatibility tests and governance gate are real and reviewable.
