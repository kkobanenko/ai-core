---
coord_version: 1
state: EXECUTOR_READY
prompt_id: persistent-coordinator-self-update-review-fix3-001
target_repo: kkobanenko/ai-core
target_branch: feat/002-persistent-coordinator-self-update-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/feat-002-persistent-coordinator-self-update-20260912
base_sha: 8317cb4aabab354d4f9ff3beeb8140658aeea5e8
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: tools/dev_coordinator/updater.py, tests/test_dev_coordinator_updater.py, docs/coordination/PERSISTENT_RUNNER.md, specs/002-persistent-coordinator-self-update/tasks.md, docs/handoffs/2026-09-12-persistent-coordinator-self-update-impl.md
required_paths: tools/dev_coordinator/updater.py, tests/test_dev_coordinator_updater.py
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "fix(coord): close updater recovery races"
---

# Architect review-fix 3 — close updater recovery/concurrency races

## Context

Exact reviewed head: `8317cb4aabab354d4f9ff3beeb8140658aeea5e8`.

Review-fix 2 correctly added pre-fetch authority checks and durable `pending_update` crash recovery, but exact code review found four merge-blocking defects. Fix these only; preserve the architecture and scope.

## 1. Do not mutate a frozen UpdateOutcome

`UpdateOutcome` is `@dataclass(frozen=True)`. Current pending/legacy recovery lock-contention paths call `_acquire_recovery_locks()` and then assign:

- `skip_outcome.local_head = ...`
- `skip_outcome.remote_head = ...`

This raises `FrozenInstanceError` at runtime.

Repair by constructing a new immutable outcome with the desired fields (or redesign the helper return shape) without mutating a frozen instance.

Regression tests must exercise both maintenance-lock and process-lock contention for pending recovery and legacy runner-start recovery and must fail if any exception is raised.

## 2. Exclusion lock must protect state loading/writing

Current `run_update_once` loads `updater-state.json` **before** acquiring `UpdaterExclusionLock`; on `updater_busy` it also calls `_persist_attempt` without owning the exclusion lock.

This creates a race: process B can load stale state while A owns the lock, fail to acquire the lock, then overwrite A's newer durable `pending_update` marker.

Required order:

1. compute state path / ensure directories;
2. acquire updater exclusion lock;
3. if unavailable, return `SKIPPED / updater_busy` **without mutating `updater-state.json`**;
4. only after successful exclusion acquisition, load the current state from disk and proceed.

Do not introduce blocking waits or reclaim semantics.

Regression test: simulate updater exclusion held while durable state changes; a second invocation returning `updater_busy` must leave state bytes/semantic content unchanged, especially `pending_update`.

## 3. Failed runner restoration after ff-only refusal must keep durable recovery

Current `merge_code != 0` + proven unchanged/clean path attempts `systemctl start`, but clears `pending_update` regardless of whether the start succeeded.

Required behavior:

- ff-only refusal + unchanged/clean + runner start succeeds: `FAIL_CLOSED / ff_refused_recoverable`, marker may be cleared because service restoration is proven.
- same git state + runner start fails: do **not** clear the marker. Record `HUMAN_REQUIRED` with an explicit recovery reason (for example `ff_refused_runner_restore_failed` or equivalent) and preserve `pending_update` so the next invocation performs bounded service recovery only, not another merge.
- next invocation after such failure must not execute `git merge`; it may make at most one protected runner-start recovery attempt.

Add a consecutive-attempt regression test.

## 4. Malformed/corrupt durable recovery state must fail closed

Current `_get_pending_update` returns `None` when `pending_update` exists but is malformed/missing fields, which makes the updater treat it as if no transaction existed and proceed normally. Also `load_updater_state` currently turns malformed JSON/read errors into a fresh empty state.

For a self-updater, losing durable recovery evidence must not silently authorize another update.

Required semantics:

- distinguish `pending_update` absent from `pending_update` present-but-invalid;
- validate required marker fields and known phase (`stop_mutation_window` or the exact supported phase constant);
- present-but-invalid marker -> `HUMAN_REQUIRED / pending_update_invalid` (or equivalent), no fetch, no systemctl, no git mutation; preserve the raw state evidence where possible;
- if an existing state file cannot be decoded/read safely, fail closed rather than treating it as a brand-new empty state. Use a strict load path for execution; status/read-only reporting may expose the error but must not erase it;
- unsupported state version should likewise fail closed rather than silently normalize, if versioning is present.

Do not delete or auto-repair corrupted state.

## Preserve all existing safety properties

Keep exactly:

- pre-fetch local authority gate;
- updater exclusion -> maintenance exclusive -> Coordinator process lock ordering;
- durable marker persisted before runner stop;
- pending target/pre-head recovery with one bounded `systemctl start` and no merge in recovery invocation;
- normal git mutation limited to `git merge --ff-only origin/<transition-branch>`;
- no reset/clean/checkout switch/rebase/stash/pull/force;
- no hosted CI, release, deployment, platform-control, consumer or `src/ai_core/**` changes.

## Required tests

At minimum add/adjust tests for:

1. pending recovery + maintenance lock contention returns `SKIPPED` without FrozenInstanceError and later recovers;
2. pending recovery + process lock contention likewise;
3. legacy start-failure recovery + both lock-contention variants likewise;
4. exclusion busy does not write or alter state, including a pending marker written by the lock owner;
5. ff refusal unchanged/clean + runner restore failure -> HUMAN_REQUIRED + marker retained; second attempt performs start-only recovery, no merge;
6. malformed pending marker (missing head, wrong type, unknown phase) -> HUMAN_REQUIRED, no fetch/systemctl/mutation;
7. corrupt existing JSON state -> fail closed, no fetch/systemctl/mutation;
8. unsupported state version -> fail closed;
9. all existing authority, normal success, crash recovery and lock-order tests remain intact.

If shell execution is available, run the focused updater tests and full gate from the handoff. If unavailable, state so explicitly; never claim green tests.

Update documentation/task bookkeeping/handoff with actual behavior and tests. Finish with concise Executor summary and stop; Coordinator owns publication.
