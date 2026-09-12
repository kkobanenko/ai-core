---
coord_version: 1
state: EXECUTOR_READY
prompt_id: persistent-coordinator-runner-review-fix1-001
target_repo: kkobanenko/ai-core
target_branch: feat/001-persistent-coordinator-runner-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/feat-001-persistent-coordinator-runner-20260912
base_sha: 7427a426897821e1bbeb1f07f9ae54978223aa86
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: tools/dev_coordinator/managed_worktrees.py, tests/test_dev_coordinator_runner.py, specs/001-persistent-coordinator-runner/tasks.md, docs/handoffs/2026-09-12-persistent-coordinator-runner.md
required_paths: tools/dev_coordinator/managed_worktrees.py, tests/test_dev_coordinator_runner.py
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "fix(coord): refresh changed bridge SHA safely"
---

# Persistent runner — Architect review fix 1

This is a narrow review repair inside the existing Spec Kit-native feature `001-persistent-coordinator-runner`.

Authoritative requirements remain:

- `specs/001-persistent-coordinator-runner/spec.md`
- `specs/001-persistent-coordinator-runner/plan.md`
- `specs/001-persistent-coordinator-runner/tasks.md`

Do not broaden scope. Do not create a new feature/spec. Do not modify runtime/provider/tracing source, dependencies, platform-control, consumers, service activation, PRs, tags, releases, or hosted CI.

## Review blocker

Architect exact-head review of `7427a426897821e1bbeb1f07f9ae54978223aa86` found that terminal state is keyed by `(bridge repo, branch, SHA)`, so a changed SHA of an existing `coord/bridge/*` branch is correctly reconsidered by discovery. However, `prepare_bridge_worktree()` only reuses a managed bridge worktree when its current HEAD already equals the new bridge SHA. A clean managed bridge worktree at the previous SHA is therefore rejected as stale instead of being safely advanced.

The current test `test_changed_sha_not_terminal` proves only state-key behavior. It does not exercise a real/prepared existing bridge worktree and therefore misses the defect.

This contradicts the Spec Kit contract that a changed bridge SHA may be reconsidered without weakening exactly-once claims.

## Required fix

Implement the smallest safe repair in `tools/dev_coordinator/managed_worktrees.py`:

1. For an EXISTING managed bridge worktree only, if all of these are true:
   - path is under the configured managed root;
   - origin repo matches the expected canonical repo;
   - checked-out branch exactly matches the bridge branch;
   - worktree is clean;
   - remote bridge branch exists and its tip is exactly the newly discovered `bridge_sha`;
   - current local HEAD differs from `bridge_sha`;
   then attempt only a fast-forward update to the exact remote/new SHA.

2. The update MUST be non-destructive and fail closed:
   - use `git merge --ff-only <bridge_sha>` or an equivalently strict fast-forward-only operation;
   - no `reset --hard`;
   - no force checkout/update;
   - no `git clean`;
   - no deletion/recreation of a dirty or inconsistent worktree;
   - a non-fast-forward update MUST fail closed.

3. After the fast-forward, re-run exact worktree verification and require repo/branch/HEAD/clean to match the requested bridge SHA.

4. Do not change executor worktree semantics in this repair unless a regression test demonstrates the same concrete requirement there. The identified blocker is specifically changed-SHA reuse of the managed bridge worktree.

## Regression tests

Extend `tests/test_dev_coordinator_runner.py` with tests that actually exercise bridge worktree preparation rather than state keys only. At minimum prove:

- existing clean managed bridge worktree at old SHA + remote same branch at a newer fast-forward SHA is advanced and returned `ok=True` at the new exact SHA;
- the update command is explicitly fast-forward-only;
- non-fast-forward / ff-only failure returns fail-closed and does not invoke reset/force/clean;
- dirty bridge worktree still fails closed and is not advanced;
- repo or branch mismatch still fails closed;
- the existing terminal-state test for changed SHA remains, but is no longer the sole evidence for reconsideration.

Prefer a real temporary git repository integration-style regression test if practical; otherwise the fake git runner must model pre/post HEAD accurately enough to prove the full path.

## Spec/handoff bookkeeping

- Update the relevant task checkbox/note in `specs/001-persistent-coordinator-runner/tasks.md` only if needed to truthfully record the review repair.
- Update `docs/handoffs/2026-09-12-persistent-coordinator-runner.md` with the Architect review finding and repair validation if useful.
- Do not claim service activation.

## Validation

Run locally if shell access is available:

1. focused new changed-SHA/worktree regression tests;
2. all `tests/test_dev_coordinator_runner.py`;
3. `tests/test_dev_coordinator_runner_install.py`;
4. existing `tests/test_dev_coordinator.py`;
5. `git diff --check`.

Do not install dependencies and do not enable/start systemd. If shell access is unavailable, state that explicitly in the handoff; Coordinator publication checks do not substitute for pytest.

Do not commit or push yourself. Coordinator owns exact-path publication.

Finish with a concise Executor summary and stop.