# AI Core Transition Baseline Design

## Purpose

Produce an evidence-backed snapshot of the current AI estate before any new
runtime work. The snapshot must make the production baseline, compatibility
boundaries, governance gates, and safe next work package unambiguous.

## Scope

This work package updates four durable documents in `ai-core`:

- `docs/migration/current_state_baseline.md` records repository, release, PR,
  test, and governance state.
- `docs/architecture/cross_project_ai_inventory.md` records every inspected
  project and the exact evidence for whether and how it uses AI.
- `docs/architecture/source_of_truth_map.md` separates temporary evidence
  owners, future canonical owners, and product-owned responsibilities.
- `docs/handoffs/2026-09-08-ai-core-transition-baseline.md` records the branch,
  SHAs, verification, risks, rollback, blockers, and next step.

The work also adds only those compatibility tests that can be derived from
the current immutable/root API contract without importing consumer code or
changing behavior.

## Evidence Model

Evidence is collected read-only from:

1. all repositories and directories under `/home/kok4444/projects`;
2. the platform-control allowlist, compatibility matrix, current initiatives,
   ADRs, and open review requests;
3. current `ai-core` main, immutable tags, historical branches, and PRs #3-#5;
4. dependency manifests, configuration, provider clients, direct network
   calls, retry/fallback logic, tracing, privacy controls, and media AI paths;
5. tests and handoffs that define observable compatibility behavior.

Every material inventory claim should cite a concrete path, revision, PR, or
command result. Unknowns remain explicit; no pending governance decision is
inferred or resolved.

## Compatibility Boundary

- Preserve the exact current root `ai_core.__all__` and tracing behavior.
- Treat immutable tags as immutable and record peeled commit SHAs.
- Treat Prozakupki and KMO as read-only evidence sources.
- Do not change consumers, provider identities, capabilities, transports,
  fallback, runtime, services, releases, tags, or infrastructure.
- Classify proposed identities and `STT_SEGMENTS` as governance-pending rather
  than canonical.
- Evaluate PRs #3-#5 as candidates only; do not merge or mark merge-ready.

## Deliverable Quality

The final documents must identify every allowlisted repository as AI-using or
non-AI, include other discovered AI consumers, distinguish observed facts from
inferences, list missing compatibility coverage, and recommend one bounded
next work package. Documentation and compatibility-only changes must pass the
supported local test baseline and `git diff --check`.

## Rollback

Drop the documentation branch. No consumer, deployment, release, immutable
tag, or production execution path is changed.
