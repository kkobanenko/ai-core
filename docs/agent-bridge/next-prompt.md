---
coord_version: 1
state: EXECUTOR_READY
prompt_id: persistent-coordinator-self-update-final-gate-test-fix-001
target_repo: kkobanenko/ai-core
target_branch: fix/002-self-update-final-gate-test-harness-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/fix-002-self-update-final-gate-test-harness-20260912
base_sha: 695ad63fe963a4baea068bdac6da1020ddbe33e0
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: tests/test_dev_coordinator_updater.py, docs/handoffs/2026-09-12-persistent-coordinator-self-update-impl.md
required_paths: tests/test_dev_coordinator_updater.py
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "test(coord): repair self-update final gate harness"
---

# Final gate test-only repair

## Context

The operator executed the exact local final gate at candidate `9f2fb0531765c345b06891bdb550dfbe0583beaf`.
Result: `2 failed, 157 passed`; `git diff --check` passed.

Two temporary bookkeeping commits after that candidate add/remove the same accidental bridge artifact; compare `9f2fb053...695ad63f` has zero changed files. This repair branch starts from `695ad63fe963a4baea068bdac6da1020ddbe33e0`, whose tree is therefore identical to the reviewed candidate.

Architect analysis concludes both failures are defects in the test harness caused by earlier reviewed safety changes. Production updater behavior must NOT be changed in this package.

## Required repairs

### 1. `TestUpdaterOrchestration.test_fetch_failure_no_mutation`

The test predates the pre-fetch local authority gate introduced in review-fix2. `run_update_once` now intentionally performs local read-only authority commands before `git fetch origin`.

Repair the test so that:
- it allows the normal local authority commands before fetch, preferably by reusing `FakeGitRepo` and overriding/delegating only `fetch origin`;
- `fetch origin` returns a network failure;
- the test still asserts `FAIL_CLOSED / fetch_error`;
- no systemctl calls occur;
- no git mutation such as merge/reset/clean/checkout/rebase/stash/pull/force occurs;
- production pre-fetch authority behavior is not weakened.

### 2. `TestUpdaterReviewFix3.test_ff_refused_runner_restore_failed_then_start_only_recovery`

The first run uses a `systemctl` recorder that increments `start_calls`. The second run currently supplies a different lambda that returns success but cannot increment that counter, making `assert start_calls == 2` impossible.

Repair the test so both start attempts are counted correctly while preserving the intended scenario:
- first start attempt fails after ff-only refusal;
- durable `pending_update` remains;
- second `run_update_once` performs start-only recovery and that start succeeds;
- no second merge occurs;
- final result remains `FAIL_CLOSED / pending_pre_merge_recovered` with `runner_started=True` and `merge_attempted=False`;
- exactly two start attempts across both runs are proven.

Do not weaken behavioral assertions merely to make the test pass.

## Hard boundaries

- Production code must not change.
- Modify `tests/test_dev_coordinator_updater.py` only unless a short handoff note is useful.
- DO NOT modify `tools/dev_coordinator/updater.py`, locks, runner, installer, configs, systemd units, `src/ai_core/**`, dependencies, platform-control, consumers, deployment, release, or governance.
- DO NOT dispatch hosted CI.
- Executor must not commit or push; Coordinator owns publication.

## Verification requested

If shell is available, run:

```bash
PYTHONPATH=. python3.10 -m pytest -q \
  tests/test_dev_coordinator_updater.py \
  tests/test_dev_coordinator_updater_install.py \
  tests/test_dev_coordinator_runner.py \
  tests/test_dev_coordinator_runner_install.py \
  tests/test_dev_coordinator.py

git diff --check d2e13bfe93f11ded0cebb5bd1285cc92d00435ad HEAD
```

If shell is unavailable, make the bounded test repair and record that final verification remains operator/Coordinator responsibility.
