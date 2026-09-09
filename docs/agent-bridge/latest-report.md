# Latest agent report

**Work package:** AI Core compatibility characterization closeout  
**Branch:** `test/ai-core-compatibility-characterization-20260909`  
**Production base:** `7569441c18362cfd15524ad73f56f7f35580c86f`  
**Content head before bridge closeout:** `a116547cad50376399e0cf6091dcbedf114d0443`  
**Delivery head:** recorded after the closeout commit using the
pre-final/final-SHA convention, because a commit cannot contain its own SHA.

## Validation status

Final validation is intentionally rerun after all bridge/report content is in
place. The closeout commit records the actual results before publication.

## Main findings

- Current `main` remains a dependency-light tracing-only nine-symbol contract.
- Immutable v0.2 tags are separate historical evidence, not a drop-in main
  replacement; `v0.2.2` has no `invoke_text` or `STT_SEGMENTS`.
- Nine consumer infrastructure contracts are pinned by exact SHA without
  importing or changing consumer code.
- `SECRET` requires zero eligible routes and zero provider attempts for every
  form/boundary; PR #3 currently conflicts for sanitized/surrogated forms.
- PR #3–#5 are OPEN/DRAFT/CI-green but not merge-authorized.
- Platform-control issues #291–#293 are OPEN review-only records with no
  approval.
- Governance has an observed-state drift: it records `83acc530...` for
  ai-core main while factual main is `7569441...`.
- GitHub branch protection is not enforced on `ai-core/main`; this is an
  operational risk, not a work-package blocker.

## PR disposition summary

- **PR #3:** keep dependency-light/root-compatible pieces; redesign all-form
  SECRET behavior; fix provider-level capability evidence; governance review
  required.
- **PR #4:** retain only corrected alias/evidence machinery for the accepted
  four IDs; split new identities and `STT_SEGMENTS` into later governed work.
- **PR #5:** keep deadline arithmetic; decide taxonomy, UNKNOWN health, order,
  and explicit egress; redesign inherited SECRET/default egress; defer
  executor/transports.

## Blockers and next package

Runtime implementation remains unauthorized. Privacy, identity/capability,
GPU boundary, route order, health, egress, error taxonomy, deadline, service
ownership, STT, and fallback-owner decisions remain open.

Recommended next work package: an explicitly authorized platform-control
governance-resolution and draft-stack decomposition package. Do not start it
until `next-prompt.md` is replaced by a new user/ChatGPT instruction.

Full report:
`docs/reports/2026-09-09-ai-core-compatibility-characterization-report.md`.
