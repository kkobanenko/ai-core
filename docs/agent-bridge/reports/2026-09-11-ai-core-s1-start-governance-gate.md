# AI Core S1 start governance gate handoff

**Date:** 2026-09-11
**Verdict:** draft gate published; exact-head CI green; no merge; no S1 source

## Result

The operator authorized only the `S1_foundation_contracts` work package. Since
authoritative `platform-control/main@35a922ceacb51ff2e8e8ccacc00291fbd2155b52`
still recorded S1 start as false, the required control-plane proposal was
created first.

Draft platform-control PR #295 records that narrow authorization:
https://github.com/kkobanenko/platform-control/pull/295

It is `OPEN`, `DRAFT`, `MERGEABLE`, and green on exact head
`44d30f1a81fe7736c83a6f49ce7fde5c91412b08`. It was not merged.

## Git handoff

- Repository: `platform-control`
- Branch: `governance/ai-core-s1-start-20260911`
- Base: `35a922ceacb51ff2e8e8ccacc00291fbd2155b52`
- Head: `44d30f1a81fe7736c83a6f49ce7fde5c91412b08`
- PR: #295, draft
- CI: Infrastructure CI `34532744201`, success
- Authoritative main after publication: unchanged at `35a922ce...`
- AI Core main: unchanged at `7569441c...`

## Scope evidence

The eight-file diff contains only coordination, operator-decision evidence,
decision documentation, and machine guards. It proposes start authorization
only for `S1_foundation_contracts` while retaining `FOUNDATION_ONLY` and a false
broad implementation flag.

Explicitly false remain runtime, service, provider transports, executor,
consumer migration, release, tag, and deployment. New identities and
`STT_SEGMENTS` remain unauthorized. The provider set remains four IDs, root API
remains nine symbols, GPU remains `UNKNOWN_BOUNDARY`, and GPU HTTP 503 remains
failed/inconclusive rather than runtime capability proof.

## Checks

- Focused governance tests: 8 passed.
- Validator: pass with known path-alias warning.
- Workstation full suite: 1792 passed, 229 skipped, three known baseline
  path-alias failures.
- Hosted exact-head suite: green through tests, validators, secret scan, Docker
  builds, and startup smoke.
- AI Core PR #3-#5 remain open/draft at their pinned heads.

## Stop condition

Satisfied. No AI Core source work may start until PR #295 is separately
authorized, merged unchanged, and authoritative platform-control main is
reverified.

Rollback before merge: close PR #295 and drop its branch. No main/runtime/
consumer rollback is required.
