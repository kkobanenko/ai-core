---
coord_version: 1
state: EXECUTOR_READY
prompt_id: persistent-coordinator-self-update-review-fix2-001
target_repo: kkobanenko/ai-core
target_branch: feat/002-persistent-coordinator-self-update-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/feat-002-persistent-coordinator-self-update-20260912
base_sha: 319524d62ffd769d9056986a61a3cfd4e02f8aed
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: tools/dev_coordinator/updater.py, tests/test_dev_coordinator_updater.py, docs/coordination/PERSISTENT_RUNNER.md, specs/002-persistent-coordinator-self-update/tasks.md, docs/handoffs/2026-09-12-persistent-coordinator-self-update-impl.md
required_paths: tools/dev_coordinator/updater.py, tests/test_dev_coordinator_updater.py
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "fix(coord): harden updater transaction recovery"
---

# Architect review-fix 2 — authority ordering + durable update recovery

## Context

Exact reviewed head: `319524d62ffd769d9056986a61a3cfd4e02f8aed`.

Review-fix 1 fixed the primary `runner_start_failed -> NOOP` downgrade, but exact-head review found three remaining merge blockers in the same self-update transaction:

1. `git fetch origin` currently happens before local authority checks. A wrong-origin/wrong-branch/dirty Coordinator checkout must fail closed before any fetch.
2. A crash/process death after runner stop or successful ff-only merge, but before runner restart/state finalization, can leave the runner stopped without durable evidence that the update transaction is incomplete.
3. During sticky recovery, a transient `maintenance_held` or `process_lock_held` result currently overwrites `HUMAN_REQUIRED` with `SKIPPED`; a later invocation can then fall through to normal `NOOP`. Temporary lock contention must not erase unresolved recovery context.

## Required repair

Implement a deterministic fail-closed transaction/recovery model. Keep it stdlib-only and narrowly scoped.

### A. Pre-fetch authority gate

Before executing `git fetch origin`, verify local authority properties that do not require network/fetched refs:

- configured Coordinator path is a git worktree;
- exact configured transition branch is checked out;
- worktree is clean;
- `origin` matches the configured expected canonical repo/URL;
- local HEAD is readable.

If any of these fail:

- return `FAIL_CLOSED` with an explicit reason (`wrong_origin`, `wrong_branch`, `dirty_worktree`, etc.);
- do **not** call `git fetch`;
- do not stop/start runner;
- do not mutate git.

Only after this local authority gate passes may `git fetch origin` occur. After fetch, read remote transition head and perform ancestry / already-current decisions.

A normal `local == remote` NOOP must therefore only occur after the local authority gate has passed.

### B. Durable pending-update marker

Persist an explicit durable recovery/transaction marker in `updater-state.json` **before stopping the runner**. Use clear fields/structure (for example a `pending_update` object) sufficient to distinguish an incomplete transaction from normal NOOP state.

At minimum persist:

- pre-update/local head;
- intended fetched target/remote head;
- a phase/state indicating the update has entered the stop/mutation window;
- enough information for a later invocation to recover without guessing.

The marker must survive ordinary result/status writes until the transaction is explicitly resolved. Do not key recovery solely from `last_result` / `reason`.

Required crash-recovery semantics on a later timer invocation, handled under the normal lock ordering (`updater exclusion -> maintenance exclusive -> Coordinator process lock`):

1. **Current HEAD == recorded target head, clean/authority-valid**: treat as merge completed but runner restart/finalization potentially incomplete. Perform at most one bounded `systemctl start <runner>` recovery attempt, with **no merge**. Success clears/resolves the marker and records explicit recovered success. Failure preserves the marker and records `HUMAN_REQUIRED`.
2. **Current HEAD == recorded pre-update head, clean/authority-valid**: transaction did not complete the git advance (for example crash after stop but before merge). Perform at most one bounded `systemctl start <runner>` to restore service. If start succeeds, resolve/clear the pending marker with an explicit fail-closed/recovered-pre-merge result; a later timer invocation may start a fresh normal update. Do not merge in the same recovery invocation. If start fails, preserve marker + `HUMAN_REQUIRED`.
3. **Dirty worktree, unexpected HEAD, wrong branch/origin, missing evidence, or otherwise uncertain**: preserve marker, do not reset/clean/force/merge/start speculatively, record `HUMAN_REQUIRED` with explicit reason.

Persist the pending marker before `systemctl stop` so a crash anywhere after stop is diagnosable/recoverable. Clear it only after a proven resolved state.

### C. Sticky recovery survives SKIPPED attempts

A transient inability to acquire maintenance/process lock must not erase unresolved recovery.

- `SKIPPED / maintenance_held` and `SKIPPED / process_lock_held` may be returned for the current invocation, but the durable pending/sticky recovery marker must remain intact.
- The next invocation must still enter recovery handling rather than ordinary `NOOP`.
- Existing uncertain post-stop HUMAN_REQUIRED states must likewise not silently disappear due to transient skip bookkeeping.

### D. Preserve existing safety properties

Keep:

- exactly one updater instance via exclusion lock;
- maintenance exclusive + Coordinator ProcessLock around recovery actions and stop/merge/start critical section;
- `git merge --ff-only origin/<transition-branch>` as the only normal git mutation;
- no reset, clean, checkout switch, rebase, stash, pull, force, auto conflict repair;
- no restart loops (max one `start` recovery attempt per updater invocation);
- normal already-current healthy state remains zero-systemctl NOOP;
- no changes to runner discovery, bridge authority, installer activation semantics, `src/ai_core/**`, platform-control, consumers, hosted CI, release/deploy.

## Regression tests

Add direct tests for all of the following. Do not weaken current assertions.

1. Wrong origin before fetch -> `FAIL_CLOSED`, and assert `fetch origin` was never called.
2. Wrong branch before fetch -> no fetch.
3. Dirty checkout before fetch -> no fetch.
4. Healthy authority + already-current -> fetch allowed, then NOOP, zero systemctl.
5. Pending marker exists with current HEAD == target -> one bounded start, no merge; success clears marker and records explicit recovered state.
6. Same case but start fails -> marker remains + HUMAN_REQUIRED; next invocation still recovers, never ordinary NOOP.
7. Pending marker with current HEAD == pre-update -> one bounded runner start only, no merge; successful service restoration resolves marker; fresh update is deferred to a later invocation.
8. Pending marker + dirty/unexpected HEAD -> HUMAN_REQUIRED, marker remains, zero destructive git/systemctl mutation.
9. Sticky `runner_start_failed` recovery while maintenance lock is busy -> current call may be SKIPPED, but a following call after lock release still performs recovery (does not become NOOP).
10. Same preservation for process-lock contention.
11. Simulate a crash boundary by pre-populating the durable marker as if process died after stop / after merge, and prove deterministic recovery without relying on `last_result` alone.
12. Existing normal ff-only success, recoverable ff refusal, uncertain ff refusal, lock ordering and updater exclusion tests remain valid.

If shell execution is available, run the focused updater tests plus the full gate documented in the handoff. If shell is unavailable, state that explicitly and do not claim tests passed.

## Documentation/bookkeeping

Update `docs/coordination/PERSISTENT_RUNNER.md` with the durable pending-update/recovery semantics, update Spec Kit task bookkeeping, and update the implementation handoff with this Architect review-fix and actual tests run.

Finish with a concise Executor summary and stop. Coordinator owns publication.
