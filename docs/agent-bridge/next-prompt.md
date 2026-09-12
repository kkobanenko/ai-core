---
coord_version: 1
state: EXECUTOR_READY
prompt_id: persistent-coordinator-self-update-review-fix1-001
target_repo: kkobanenko/ai-core
target_branch: feat/002-persistent-coordinator-self-update-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/feat-002-persistent-coordinator-self-update-20260912
base_sha: 59973911dd4e6186f66aabbf65909cf9a6c95858
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths:
  - tools/dev_coordinator/updater.py
  - tests/test_dev_coordinator_updater.py
  - specs/002-persistent-coordinator-self-update/tasks.md
  - docs/handoffs/2026-09-12-persistent-coordinator-self-update-impl.md
required_paths:
  - tools/dev_coordinator/updater.py
  - tests/test_dev_coordinator_updater.py
transient_paths:
  - uv.lock
publication:
  commit: true
  push: true
  commit_message: "fix(coord): preserve updater recovery state"
---

# Architect review-fix 1 — sticky post-stop recovery state

## Context

Exact reviewed implementation head: `59973911dd4e6186f66aabbf65909cf9a6c95858`.

Architect found a merge-blocking recovery bug in `run_update_once`:

1. an ff-only update can succeed;
2. runner restart can fail, producing `HUMAN_REQUIRED / runner_start_failed` while local HEAD already equals remote HEAD and the runner remains stopped;
3. the next timer cycle currently takes the early `local_head == remote_head` path and writes `NOOP / already_current` without checking the prior terminal recovery state or whether the runner was restored;
4. this can erase the actionable `HUMAN_REQUIRED` evidence while leaving the persistent runner stopped indefinitely.

A similar rule applies to other post-stop `HUMAN_REQUIRED` states: an `already_current` git state must not silently downgrade unresolved operational recovery evidence.

## Required repair

Implement deterministic, fail-closed sticky recovery semantics.

Minimum required behavior:

- The early `local_head == remote_head` NOOP path MUST NOT overwrite unresolved post-stop `HUMAN_REQUIRED` state.
- Specifically cover `runner_start_failed` after a successful merge. On a later timer cycle, if local/remote still match the recorded successful head and git preconditions are clean/safe, the updater MAY perform one bounded runner-start recovery attempt under the normal maintenance-exclusive + Coordinator-process locks. If that start succeeds, record a clear recovered terminal outcome/reason without attempting another merge. If it fails, keep `HUMAN_REQUIRED`; do not downgrade to `NOOP`.
- For post-stop `HUMAN_REQUIRED` reasons whose git state is dirty/uncertain (for example `post_merge_dirty` or unresolved `ff_refused`), never auto-repair/reset/clean/force. Preserve `HUMAN_REQUIRED` until a later attempt can prove a specifically authorized safe recovery, otherwise remain fail-closed.
- A normal clean already-current installation with no unresolved post-stop recovery state must remain `NOOP` with zero stop/start/merge actions.
- Do not add restart loops. At most one recovery start attempt per timer invocation.
- Preserve lock ordering: updater exclusion -> maintenance exclusive -> Coordinator process lock. Do not start/stop the runner outside the protected recovery window when a recovery action is taken.
- Preserve all existing git restrictions: no reset, clean, force, checkout switch, rebase, stash, pull, or non-origin fetch.

## Regression tests

Add direct tests that execute consecutive updater attempts against the same persisted state:

1. First attempt: ff-only succeeds, runner `start` fails -> `HUMAN_REQUIRED / runner_start_failed`.
2. Second attempt with local==remote:
   - must NOT become `NOOP` merely because heads match;
   - if recovery start succeeds, verify exactly one bounded start attempt, no merge, and explicit recovered state;
   - if recovery start fails again, verify `HUMAN_REQUIRED` remains sticky and no merge occurs.
3. A normal already-current state without unresolved recovery remains `NOOP` and performs zero systemctl actions.
4. A persisted dirty/uncertain post-stop `HUMAN_REQUIRED` must not be silently cleared by local==remote.

Do not weaken existing assertions.

## Scope boundaries

Do not change:

- `tools/dev_coordinator/locks.py` or lock ordering unless a new focused test proves it is necessary for this repair;
- runner discovery/publication semantics;
- installer/systemd units;
- `src/ai_core/**`;
- platform-control or consumer repositories;
- hosted CI, releases, tags, deployment.

Update Spec Kit task bookkeeping and implementation handoff to record this Architect review repair. If shell execution is available, run the focused updater tests and the full required local gate from the handoff. If shell is unavailable, state that explicitly; do not claim tests passed.
