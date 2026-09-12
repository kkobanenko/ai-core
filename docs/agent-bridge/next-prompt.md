---
coord_version: 1
state: EXECUTOR_READY
prompt_id: persistent-runner-stale-worktree-guard-001
target_repo: kkobanenko/ai-core
target_branch: fix/persistent-runner-stale-worktree-guard-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/fix-persistent-runner-stale-worktree-guard-20260912
base_sha: d8390a68ddc4cacc7a893d3f818808cf9179af95
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: tools/dev_coordinator/managed_worktrees.py, tests/test_dev_coordinator_runner.py, specs/001-persistent-coordinator-runner/tasks.md, docs/handoffs/2026-09-12-persistent-runner-stale-worktree-guard.md
required_paths: tools/dev_coordinator/managed_worktrees.py, tests/test_dev_coordinator_runner.py
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "fix(coord): tolerate stale missing worktrees"
---

# Persistent Coordinator runner — stale worktree guard repair

This is a bounded repair under the existing authoritative Spec Kit package `specs/001-persistent-coordinator-runner/*`. The bridge is execution transport only and does not redefine requirements.

## Observed commissioning defect

The persistent runner can crash an entire scan while checking branch collisions if `git worktree list --porcelain` contains an old registered worktree whose directory no longer exists. The observed failure was `FileNotFoundError` while `read_worktree_snapshot()` attempted to run git with cwd `/tmp/ai-core-task2`. Because the exception escapes `process_candidate`, `last_scan_at` is never recorded and no candidate is processed.

A separate known unit-test defect remains in `test_bridge_ff_only_failure_is_fail_closed`: it checks forbidden `-f` as a substring of a flattened command string, so the safe argument `--ff-only` is falsely rejected.

## Required repair

1. In `tools/dev_coordinator/managed_worktrees.py`, make the branch-collision scan robust to registered worktree paths that are no longer directories.
   - Do not execute git commands with a missing/non-directory worktree path as cwd.
   - Skip such stale paths for the purpose of checking whether the requested branch is actively checked out outside the managed root.
   - Do not delete/prune/reset/clean any worktree or git metadata in code.
   - Preserve fail-closed behavior for existing worktrees, branch mismatches, dirty worktrees, remote-SHA mismatches, and `git worktree add` failures.
   - A stale registration for the requested branch may still cause the later safe `git worktree add` to fail; that is acceptable. The key requirement is that one stale path must not throw an exception that aborts the entire scan.

2. Add a regression test in `tests/test_dev_coordinator_runner.py` proving an unrelated missing stale worktree entry does not cause `prepare_bridge_worktree()` / collision checking to invoke git in that missing directory and does not crash preparation of a valid candidate.

3. Repair `test_bridge_ff_only_failure_is_fail_closed` so forbidden operations are checked by command/argv token semantics, not substring matching.
   - `merge --ff-only <sha>` must remain allowed and must still be observed in the failed-fast-forward scenario.
   - Exact destructive commands/flags such as command `reset`, `clean`, `checkout`, or argv tokens `-f` / `--force` must remain forbidden.

4. If the Executor shell is available, run:
   `PYTHONPATH=. python3.10 -m pytest -q tests/test_dev_coordinator_runner.py tests/test_dev_coordinator_runner_install.py tests/test_dev_coordinator.py`
   and `git diff --check d8390a68ddc4cacc7a893d3f818808cf9179af95 HEAD`.
   If shell is unavailable, state that explicitly in the handoff; do not fabricate test results.

5. Update `specs/001-persistent-coordinator-runner/tasks.md` only to record this commissioning repair if useful. Create `docs/handoffs/2026-09-12-persistent-runner-stale-worktree-guard.md` with concise scope, exact base, tests actually run, risks, and rollback.

## Hard boundaries

Do not modify `src/ai_core/**`, dependencies, providers, runtime routing, consumers, platform-control, service configuration, systemd unit, installer, GitHub Actions, releases, tags, or deployment.

Do not run hosted CI. Do not create PRs, merge branches, delete branches, prune worktrees, or alter claims/state files.

Do not commit or push yourself. Coordinator owns exact-path commit/push/remote verification.

Finish with a concise Executor summary and stop.
