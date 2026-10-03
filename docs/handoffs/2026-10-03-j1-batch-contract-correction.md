# J1 canonical batch-contract correction

**Date:** 2026-10-03

Repository: kkobanenko/ai-core

Branch: fix/j1-canonical-batch-contract

Base SHA: 10075dc61c4a8cbe7874fd3047eeec868946518f

Implementation HEAD: 18276c4a71edc61e9df68e59b06d65bef028896e

Scope: correct merged J1 to the batch-first contract

Authority: CORRECT_J1_CONTRACT_SEMANTICS_TYPESAFE_MAPPING

Evidence: platform-control 717cace0d109105c406723de30cd72e4e3ed7dd4
coordination/initiatives/platform-factory-global-roadmap/evidence/operator-decision-j1-contract-semantics-correction.yaml

Execution mode: mock_judgment only

The Implementation HEAD above is the final code/test snapshot.

A later documentation-only handoff synchronization commit may be the PR review head. That documentation-only successor contains no runtime implementation changes.

The PR exact reviewed head is recorded by GitHub PR #35 review/merge evidence.

## Closing commits

- 207f456f07bf37ede6cf509e50b0803ed2ec3669 — initial canonical batch correction
- 684684ab58b7c51bb90651788065522bea57ccff — answer structural validation and ordered question/answer serialization
- 18276c4a71edc61e9df68e59b06d65bef028896e — ordered probability serialization and final runtime/test correction

## What changed

The incorrect provider-neutral Noul draft is removed. A request holds named Binary, Choice, and Score questions. A successful response has one matching answer per question. Questions, answers, and probability entries are JSON arrays so tuple order survives `sort_keys`. Binary answers carry probability_true and do not become booleans. TypeSafe Noul is documentation-only future mapping to that probability.

## Tests

- targeted J1 tests: 23 passed
- python3.10 -m pytest -q: 405 passed
- git diff --check: pass
- CI: SUCCESS on 18276c4a71edc61e9df68e59b06d65bef028896e

## Risks

J1 remains mock-only. Real providers stay blocked. JUDGMENT admission is not implemented. The decision-pack resolver only checks identity and version. Deadline still depends on a monotonic clock. No deployment occurred.

## Rollback

Primary rollback: revert the eventual PR #35 merge.

Implementation snapshot: 18276c4a71edc61e9df68e59b06d65bef028896e

Reverting only an earlier intermediate commit does not remove the whole correction. Provider catalog behavior is unchanged. There is no deployment to roll back.

## Not implemented

J2, typesafe_jev, credentials, network calls, ProviderCapability.JUDGMENT, provider admission, consumer migration.
