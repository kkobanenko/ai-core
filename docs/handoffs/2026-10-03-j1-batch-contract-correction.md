# J1 canonical batch-contract correction

**Date:** 2026-10-03

Repository: kkobanenko/ai-core

Branch: fix/j1-canonical-batch-contract

Base SHA: 10075dc61c4a8cbe7874fd3047eeec868946518f

Implementation HEAD: 207f456f07bf37ede6cf509e50b0803ed2ec3669

Scope: correct merged J1 to the batch-first contract

Authority: CORRECT_J1_CONTRACT_SEMANTICS_TYPESAFE_MAPPING

Evidence: platform-control 717cace0d109105c406723de30cd72e4e3ed7dd4
coordination/initiatives/platform-factory-global-roadmap/evidence/operator-decision-j1-contract-semantics-correction.yaml

Execution mode: mock_judgment only

## What changed

Provider-neutral Noul is removed. A request holds named Binary, Choice, and Score questions. A successful response has one matching answer per question. Binary answers carry probability_true and do not become booleans. TypeSafe Noul is documentation-only future mapping to that probability.

## Tests

python3.10 -m pytest -q: 400 passed

git diff --check: pass

## Risks

J1 remains mock-only. Real providers stay blocked. JUDGMENT admission is not implemented. The decision-pack resolver only checks identity and version. Deadline still depends on a monotonic clock. No deployment occurred.

## Rollback

Revert this corrective branch or its merge. That restores the merged PR #34 contract, including the incorrect provider-neutral Noul API. Provider catalog behavior is unchanged. There is no deployment to roll back.

## Not implemented

J2, typesafe_jev, credentials, network calls, ProviderCapability.JUDGMENT, provider admission, consumer migration.
