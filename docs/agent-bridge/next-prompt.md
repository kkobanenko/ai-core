---
coord_version: 1
state: EXECUTOR_READY
prompt_id: self-update-runner-state-atomic-write-001
target_repo: kkobanenko/ai-core
target_branch: fix/002-self-update-runner-state-atomic-write-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/fix-002-self-update-runner-state-atomic-write-20260912
base_sha: b52a3e565c466e471bf719bd9bc30069ade8ce8c
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: tools/dev_coordinator/runner.py, tests/test_dev_coordinator_updater.py, tests/test_dev_coordinator_runner.py
required_paths: tools/dev_coordinator/runner.py
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "fix(coord): make runner state atomic writes concurrency-safe"
---

# Work package: runner-state atomic write concurrency fix

The operator's real local final gate failed with 1 test failure after 158 passes:
`TestUpdaterLocks.test_concurrent_lock_ordering_no_deadlock` raised `ENOENT` while replacing `runner-state.json.tmp`.

## Diagnosis

`save_runner_state()` currently uses one deterministic temporary path (`runner-state.json.tmp`). Two concurrent runner writers can race: one `os.replace()` removes the shared temp path and the other writer then fails with `ENOENT`.

This is a real tooling-plane concurrency defect, not a new feature.

## Required change

1. In `tools/dev_coordinator/runner.py`, make `save_runner_state()` use a unique temporary file for each writer, created in the SAME directory as the destination so `os.replace()` stays atomic on one filesystem.
2. Preserve the final JSON format and destination path exactly.
3. Keep `os.replace()` as the publication operation.
4. Best-effort clean up only the temp file created by that writer if an exception occurs or after replace if it somehow remains.
5. Do not use a shared deterministic `.tmp` filename.
6. Do not add reset/clean/checkout/rebase/stash/pull/force behavior.
7. Do not change `tools/dev_coordinator/updater.py` or any product/runtime code.

## Tests

Add/adjust focused regression coverage proving concurrent calls cannot collide on one temp path and the final `runner-state.json` remains valid JSON. The existing `TestUpdaterLocks.test_concurrent_lock_ordering_no_deadlock` must remain meaningful and pass without weakening its concurrency assertion.

If shell execution is available, run at least:

`PYTHONPATH=. python3.10 -m pytest -q tests/test_dev_coordinator_updater.py tests/test_dev_coordinator_runner.py`

and `git diff --check b52a3e565c466e471bf719bd9bc30069ade8ce8c HEAD`.

## Boundaries

- Bootstrap/reconciliation fix only under the transition freeze.
- No new Coordinator feature.
- No `src/ai_core/**`.
- No platform-control/consumer/deployment/release changes.
- No hosted CI.
- Executor must not commit or push; Coordinator owns publication.
