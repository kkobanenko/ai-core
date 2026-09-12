---
coord_version: 1
state: EXECUTOR_READY
prompt_id: persistent-coordinator-runner-review-fix2-001
target_repo: kkobanenko/ai-core
target_branch: feat/001-persistent-coordinator-runner-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/feat-001-persistent-coordinator-runner-20260912
base_sha: 4ebe7d92c66722d20dd2f929c61f52441779e393
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: tools/dev_coordinator/runner_config.py, tests/test_dev_coordinator_runner.py, specs/001-persistent-coordinator-runner/tasks.md, docs/handoffs/2026-09-12-persistent-coordinator-runner.md
required_paths: tools/dev_coordinator/runner_config.py, tests/test_dev_coordinator_runner.py
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "fix(coord): repair runner config and test harness"
---

# Persistent runner — Architect review fix 2

This is a narrow repair inside the existing Spec Kit-native feature `001-persistent-coordinator-runner` after the first real local pytest gate.

Authoritative feature requirements remain in:
- `specs/001-persistent-coordinator-runner/spec.md`
- `specs/001-persistent-coordinator-runner/plan.md`
- `specs/001-persistent-coordinator-runner/tasks.md`

Do not broaden scope. PR #8 remains draft until this repair and the complete local test suite pass.

## Observed local gate

Exact head tested: `4ebe7d92c66722d20dd2f929c61f52441779e393`.

Command:

```bash
PYTHONPATH=. python3.10 -m pytest -q \
  tests/test_dev_coordinator_runner.py \
  tests/test_dev_coordinator_runner_install.py \
  tests/test_dev_coordinator.py
```

Result: `6 failed, 88 passed`; `git diff --check` was clean.

## Real production defect

`parse_runner_config()` currently calls `Path(...).expanduser().resolve()` before checking whether a configured path was absolute. A relative value such as `relative/path` therefore becomes an absolute cwd-derived path and fails later as non-existing rather than being rejected as a relative path.

Fix this for ALL path-valued runner configuration fields, not just the one test case:
- `coordinator_repo_root`
- `managed_worktree_root`
- `agent_bin`
- every repository clone path in `repositories`

Required semantics:
1. Preserve `~` expansion if desired, but validate that the path is absolute BEFORE `.resolve()` can convert a relative path into an absolute one.
2. Relative paths must fail closed with an error containing `absolute path`.
3. Existing-dir/file checks remain after absolute-path validation.
4. No fallback to cwd-relative interpretation.
5. No dependency changes.

## Five failing tests are fake-git harness defects

Architect review of the failure traces and test source found malformed command matching in fake runners. Examples include:
- `cmd[:2] == ["remote", "get-url", "origin"]` — impossible because a two-element slice cannot equal a three-element list;
- `cmd[:2] == ["for-each-ref"]` — impossible once the actual command has additional arguments;
- `args[:2] == ("for-each-ref",)` — list/tuple and arity mismatch.

These bad predicates cause the fakes to return empty/default outputs, which then manufacture failures in repo canonicalization, discovery, worktree creation/reuse, changed-SHA fast-forward, and serial execution.

Repair the test harness predicates to match the actual command shape precisely enough to model production behavior. Do NOT weaken production fail-closed checks merely to satisfy the tests.

Specifically repair the failing tests:
- `TestManagedWorktrees.test_prepare_and_reuse_bridge_worktree`
- `TestManagedWorktrees.test_bridge_worktree_fast_forward_on_changed_sha`
- `TestRunnerDiscovery.test_discover_only_coord_bridge_refs`
- `TestRunnerDiscovery.test_ignore_test_prefix_branches_in_scan`
- `TestRunnerSerialAndErrors.test_serial_execution`

Retain the review-fix1 regression guarantees:
- changed managed bridge SHA advances only via `git merge --ff-only <exact SHA>`;
- dirty/diverged/repo-mismatch/branch-mismatch fail closed;
- no reset/force/clean destructive shortcuts.

## Test quality requirement

Do not simply patch assertions to green. Make the fake git runner command matchers realistic and internally coherent:
- normalize `args` to `list(args)` before matching;
- match prefixes with the correct slice length (`cmd[:3]`, `cmd[:1]`, etc.);
- ensure the fake state changes after worktree creation and ff-only merge so post-verification observes the new branch/SHA;
- keep unexpected commands visible/fail-fast where practical rather than silently returning success for everything.

Add/adjust a direct runner-config test proving each path-valued field rejects a relative path, or parameterize the existing test so the production invariant is covered comprehensively.

## Bookkeeping

Update `specs/001-persistent-coordinator-runner/tasks.md` and/or `docs/handoffs/2026-09-12-persistent-coordinator-runner.md` only as needed to record this real local test gate and repair. Do not claim activation or merge.

## Validation

If shell access is available, run exactly:

```bash
PYTHONPATH=. python3.10 -m pytest -q \
  tests/test_dev_coordinator_runner.py \
  tests/test_dev_coordinator_runner_install.py \
  tests/test_dev_coordinator.py

git diff --check \
  8430a887ae063fbc1cf29a3fcf902083355c1a36 \
  HEAD
```

Expected: all tests pass, diff check clean.

If shell access is unavailable, state that explicitly; publication validation is not a substitute for pytest.

## Boundaries

- Do NOT modify `managed_worktrees.py` unless a new failing test proves a production defect there; review-fix1 code is currently considered correct.
- Do NOT modify `runner.py` unless a new failing test proves a production defect there.
- Do NOT change `src/**`, dependencies, platform-control, consumers, release/tag/deployment, service activation, hosted CI, or PR metadata.
- Do NOT commit or push yourself. Coordinator owns exact-path publication.

Finish with a concise Executor summary and stop.
