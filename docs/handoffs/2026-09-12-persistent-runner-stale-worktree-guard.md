# Handoff: Persistent runner stale worktree guard

Date: 2026-09-12

## Scope

Commissioning repair under `specs/001-persistent-coordinator-runner/*`: branch-collision scan no longer aborts when `git worktree list --porcelain` includes a registered path whose directory is missing. Also fixes `test_bridge_ff_only_failure_is_fail_closed` to check argv tokens instead of substring matching (so `--ff-only` is not falsely rejected).

## Branch and SHAs

| Field | Value |
| --- | --- |
| Branch | `fix/persistent-runner-stale-worktree-guard-20260912` |
| Base SHA | `d8390a68ddc4cacc7a893d3f818808cf9179af95` |
| Head SHA | *(Coordinator publication commit — not set by Executor)* |

## Changed files

- `tools/dev_coordinator/managed_worktrees.py` — skip non-directory worktree paths in `_branch_checked_out_outside_managed` before calling `read_worktree_snapshot`
- `tests/test_dev_coordinator_runner.py` — `test_stale_missing_worktree_does_not_abort_bridge_prepare`; argv-token fix in `test_bridge_ff_only_failure_is_fail_closed`
- `specs/001-persistent-coordinator-runner/tasks.md` — T025a commissioning repair note

## Tests run (Executor)

| Check | Command | Result |
| --- | --- | --- |
| Local gate | `PYTHONPATH=. python3.10 -m pytest -q tests/test_dev_coordinator_runner.py tests/test_dev_coordinator_runner_install.py tests/test_dev_coordinator.py` | **Shell unavailable** — Coordinator must run |
| Whitespace | `git diff --check d8390a68ddc4cacc7a893d3f818808cf9179af95 HEAD` | **Shell unavailable** — Coordinator must run |

## Risks

- A stale git registration for the requested branch can still cause `git worktree add` to fail later; this repair only prevents scan-wide `FileNotFoundError` from missing unrelated stale paths.
- Fail-closed behavior for live worktrees (branch mismatch, dirty, remote SHA mismatch, outside-managed collision) is unchanged.

## Rollback

Revert the publication commit on `fix/persistent-runner-stale-worktree-guard-20260912` (or drop the branch). No schema, service, or deployment changes.
