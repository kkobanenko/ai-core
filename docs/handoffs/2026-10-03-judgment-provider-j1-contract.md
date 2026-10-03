# Judgment Provider J1 contract handoff

**Date:** 2026-10-03

Repository: kkobanenko/ai-core

PR: #34

Branch: feat/judgment-provider-j1-contract

Base SHA: a9548797c420b2a9d8b158b97a4cd48306c544db

Implementation HEAD: IMPLEMENTATION_SHA_PENDING

Scope: J1 contract_only

Authority: AUTHORIZE_J1_CONTRACT_ONLY

Execution mode: mock_judgment only

## Explicitly not implemented

- J2
- real provider execution
- ProviderCapability.JUDGMENT
- provider admission
- credentials
- network calls
- deployment
- consumer integration

## Implemented behavior

`invoke_judgment` checks the typed request, privacy, a caller-supplied decision-pack resolver, and one monotonic deadline, then runs only the repository mock `mock_judgment`. A clock sample that is invalid or earlier than the previous accepted sample returns `deadline_exhausted` and does not continue resolver, mock, or result exposure. A resolver `TimeoutError` while the total deadline is still open returns `invalid_request`. A resolver timeout that reaches the total deadline returns `deadline_exhausted`.

## Verification / tests

- `python3.10 -m pytest -q`: 475 passed
- `git diff --check`: pass
- Focused regressions: `test_round_7_fail_closed_on_transient_invalid_initial_clock`, `test_round_8_reject_regressing_clock`, `test_round_9_clock_order_equivalence`, `test_round_8_separate_resolver_timeout_from_budget_expiry`, `test_round_9_resolver_failure_matrix`, `test_round_1_resolver_deadline_bounded`

## Known risks

- J1 is mock-only
- real providers remain blocked
- JUDGMENT admission is not implemented
- consumer decision-pack resolver remains external/trusted input
- deadline depends on monotonic clock validity
- no deployment or production provider activation occurred

## Rollback

Revert the PR #34 merge, or revert the implementation commit named above. That removes the J1 callable mock-only contract. Existing provider catalog behavior stays as it was on the base SHA. No deployment rollback exists because this change did not deploy.

## Remaining deferred work

J2, real provider execution, `ProviderCapability.JUDGMENT`, provider admission, credentials, network calls, deployment, and consumer integration stay unauthorized.
