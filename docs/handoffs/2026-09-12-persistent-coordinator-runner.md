# Handoff: Persistent Coordinator Runner

Date: 2026-09-12

## Branch and SHAs

| Field | Value |
| --- | --- |
| Branch | `feat/001-persistent-coordinator-runner-20260912` |
| Base SHA | `7427a426897821e1bbeb1f07f9ae54978223aa86` |
| Head SHA | *(Coordinator publication commit — not set by Executor)* |

## Architect review fix 1 (2026-09-12)

**Finding**: `prepare_bridge_worktree()` rejected a clean managed bridge worktree at an old SHA as stale instead of ff-only advancing to a newly discovered bridge SHA. Terminal state keyed by `(repo, branch, SHA)` allowed reconsideration, but worktree reuse did not.

**Repair**: For existing managed bridge worktrees only, when repo/branch/clean match and remote tip equals the new SHA, run `git merge --ff-only <bridge_sha>`, re-verify, and return `ok=True`. Non-ff, dirty, or mismatch cases remain fail-closed (no reset/force/clean).

**Regression tests**: `test_bridge_worktree_fast_forward_on_changed_sha`, `test_bridge_ff_only_failure_is_fail_closed`, `test_dirty_bridge_worktree_not_advanced`, `test_bridge_repo_or_branch_mismatch_fail_closed` in `tests/test_dev_coordinator_runner.py`.

## Changed files (allowed paths)

- `tools/dev_coordinator/runner_config.py` — strict JSON config parser
- `tools/dev_coordinator/managed_worktrees.py` — safe managed worktree prep
- `tools/dev_coordinator/runner.py` — poll/discover/schedule/delegate loop
- `scripts/install_dev_coordinator_runner.py` — idempotent user-systemd installer
- `ops/systemd/ai-core-dev-coordinator-runner.service.in` — unit template
- `tests/test_dev_coordinator_runner.py` — runner/config/worktree tests
- `tests/test_dev_coordinator_runner_install.py` — installer tests
- `docs/coordination/PERSISTENT_RUNNER.md` — architecture, safety, activation
- `docs/coordination/TRANSITION_PLAN.md` — S2A finished / Spec Kit-native note
- `specs/001-persistent-coordinator-runner/tasks.md` — checkbox updates
- `specs/001-persistent-coordinator-runner/quickstart.md` — aligned with implementation

## Tests run (Executor)

| Check | Command | Result |
| --- | --- | --- |
| Changed-SHA bridge worktree tests | `PYTHONPATH=. pytest tests/test_dev_coordinator_runner.py::TestManagedWorktrees::test_bridge_worktree_fast_forward_on_changed_sha tests/test_dev_coordinator_runner.py::TestManagedWorktrees::test_bridge_ff_only_failure_is_fail_closed tests/test_dev_coordinator_runner.py::TestManagedWorktrees::test_dirty_bridge_worktree_not_advanced tests/test_dev_coordinator_runner.py::TestManagedWorktrees::test_bridge_repo_or_branch_mismatch_fail_closed -q` | Shell unavailable in Executor session; Coordinator must run |
| All runner tests | `PYTHONPATH=. pytest tests/test_dev_coordinator_runner.py -q` | Shell unavailable in Executor session; Coordinator must run |
| Installer tests | `PYTHONPATH=. pytest tests/test_dev_coordinator_runner_install.py -q` | Shell unavailable in Executor session; Coordinator must run |
| Existing Coordinator suite | `PYTHONPATH=. pytest tests/test_dev_coordinator.py -q` | Shell unavailable in Executor session; Coordinator must run |
| Whitespace | `git diff --check` | Shell unavailable in Executor session; Coordinator must run |

## Risks

- Managed worktree path scheme must match Architect-declared `target_worktree` exactly; mismatches fail closed.
- Branch checked out outside managed root blocks package until operator resolves collision.
- Runner terminal state is scheduling idempotency only; Coordinator claim remains authoritative for exactly-once execution.
- Network outages delay detection; no package state is manufactured on fetch failure.
- Service activation changes workstation behavior; operator must run installer with `--enable` explicitly after review.

## Rollback

1. `systemctl --user disable --now ai-core-dev-coordinator-runner.service` (if enabled).
2. Remove or retain `~/.config/ai-core-dev-coordinator/runner.json` and runner state as desired.
3. Revert feature branch / publication commit.
4. Manual one-shot Coordinator remains available throughout.

## Operational notes

- **Service activation NOT performed** by Executor or implementation tests.
- **Hosted CI NOT requested** (`hosted_ci: forbidden` preserved).
- **Publication commit/push** owned by Coordinator after Executor exit; Executor did not commit or push.
