# Handoff: Persistent Coordinator Self-Update (implementation)

Date: 2026-09-12

## Branch and SHAs

| Field | Value |
| --- | --- |
| Branch | `feat/002-persistent-coordinator-self-update-20260912` |
| Base SHA | `d2e13bfe93f11ded0cebb5bd1285cc92d00435ad` |
| Head SHA | *(pending Coordinator publication commit after review-fix 2)* |
| Review-fix 1 base | `59973911dd4e6186f66aabbf65909cf9a6c95858` |
| Review-fix 2 base | `319524d62ffd769d9056986a61a3cfd4e02f8aed` |

## Summary

Implemented fail-closed Coordinator tooling self-update per `specs/002-persistent-coordinator-self-update/*`:

- Strict `updater_config.py` with runner compatibility checks
- `MaintenanceGateLock` (shared/exclusive) and `UpdaterExclusionLock` in `locks.py`
- `updater.py` oneshot orchestration with injectable git/systemctl
- Runner cooperation via `scan_with_maintenance_gate` (shared lock before scan)
- systemd updater service + timer templates
- Installer extension with `--enable-updater` bootstrap flag
- Fake-only tests for git, locks, systemctl, installer, and state persistence

### Architect review-fix 1 (sticky post-stop recovery)

- Early `local_head == remote_head` path no longer overwrites unresolved post-stop `HUMAN_REQUIRED` with `NOOP / already_current`.
- `runner_start_failed` after successful ff-only merge: next timer cycle may perform one bounded `systemctl start` under maintenance exclusive + process lock when git preconditions are clean; success records `SUCCESS / runner_start_recovered` without merge; failure stays `HUMAN_REQUIRED`.
- Uncertain post-stop reasons (`ff_refused`, `post_merge_dirty`, `post_merge_verification_failed`) remain sticky fail-closed when heads match.
- Added `TestUpdaterStickyRecovery` consecutive-attempt regression tests.

### Architect review-fix 2 (authority ordering + durable update recovery)

- **Pre-fetch authority gate**: `_check_local_authority` runs before `git fetch origin`. Wrong origin/branch/dirty/not-a-worktree/head-unavailable → `FAIL_CLOSED` with no fetch, no systemctl, no git mutation.
- **Durable `pending_update` marker**: written to `updater-state.json` before `systemctl stop` with `pre_update_head`, `target_head`, `phase`, `entered_at`. Cleared only on proven resolution.
- **Crash recovery** (first step after exclusion lock, before fetch):
  - HEAD == `target_head` + clean authority → one bounded start, no merge; success → `SUCCESS / pending_merge_recovered`, marker cleared.
  - HEAD == `pre_update_head` + clean authority → one bounded start, no merge; success → `FAIL_CLOSED / pending_pre_merge_recovered`, marker cleared (fresh update deferred).
  - Unexpected/dirty/authority failure → `HUMAN_REQUIRED`, marker preserved.
- **Sticky SKIPPED preservation**: transient `maintenance_held` / `process_lock_held` during recovery returns `SKIPPED` to caller but preserves `pending_update` and sticky `last_result`/`reason` in durable state.
- Legacy `runner_start_failed` path retained for states without `pending_update`; new failures after merge set `pending_update` automatically.
- Added `TestUpdaterPendingRecovery` and extended authority/recovery regression tests (12 architect cases).

## Changed files

| Path | Change |
| --- | --- |
| `tools/dev_coordinator/updater_config.py` | new |
| `tools/dev_coordinator/updater.py` | new; review-fix 1 + review-fix 2 |
| `tools/dev_coordinator/locks.py` | extended |
| `tools/dev_coordinator/runner.py` | maintenance gate wrapper |
| `scripts/install_dev_coordinator_runner.py` | updater install + flags |
| `ops/systemd/ai-core-dev-coordinator-updater.service.in` | new |
| `ops/systemd/ai-core-dev-coordinator-updater.timer.in` | new |
| `tests/test_dev_coordinator_updater.py` | new; review-fix 1 + review-fix 2 tests |
| `tests/test_dev_coordinator_updater_install.py` | new |
| `docs/coordination/PERSISTENT_RUNNER.md` | self-update + pending recovery |
| `specs/002-persistent-coordinator-self-update/tasks.md` | T033b bookkeeping |
| `docs/handoffs/2026-09-12-persistent-coordinator-self-update-impl.md` | this file |

## Tests

**Requested (Coordinator / operator should run locally):**

```bash
PYTHONPATH=. python3.10 -m pytest -q \
  tests/test_dev_coordinator_updater.py \
  tests/test_dev_coordinator_updater_install.py \
  tests/test_dev_coordinator_runner.py \
  tests/test_dev_coordinator_runner_install.py \
  tests/test_dev_coordinator.py

git diff --check d2e13bfe93f11ded0cebb5bd1285cc92d00435ad HEAD
```

**Review-fix 2 gate (Coordinator / operator should run locally):**

```bash
PYTHONPATH=. python3.10 -m pytest -q \
  tests/test_dev_coordinator_updater.py \
  tests/test_dev_coordinator_updater_install.py \
  tests/test_dev_coordinator_runner.py \
  tests/test_dev_coordinator_runner_install.py \
  tests/test_dev_coordinator.py

git diff --check 319524d62ffd769d9056986a61a3cfd4e02f8aed HEAD
```

**Executor session (review-fix 2):** shell commands unavailable/rejected; tests authored but not executed. Coordinator must verify before merge.

## Risks

| Risk | Mitigation |
| --- | --- |
| Runner stopped after failed ff-only with dirty/uncertain state | `HUMAN_REQUIRED`; `pending_update` preserved; no auto reset/clean |
| Crash after stop/merge before start | `pending_update` marker enables deterministic recovery on next tick |
| `runner_start_failed` erased by next `NOOP` cycle | `pending_update` + sticky `last_result` preservation on SKIPPED |
| Wrong-origin fetch before authority check (review-fix 2) | Pre-fetch gate blocks fetch entirely |
| Manual one-shot races updater before process lock | Updater holds process lock in critical section |
| Runner starts under updater maintenance exclusive | Runner skips scans until exclusive released |
| Legacy states without `pending_update` | Legacy `runner_start_failed` recovery path retained |

## Rollback

1. Disable updater only (runner continues on last known-good checkout):

```bash
systemctl --user disable --now ai-core-dev-coordinator-updater.timer
systemctl --user disable --now ai-core-dev-coordinator-updater.service
```

2. Disable runner as well if needed:

```bash
systemctl --user disable --now ai-core-dev-coordinator-runner.service
```

3. Revert implementation commit on transition branch if git state is clean and operator authorizes manual checkout repair.

4. If `pending_update` marker is stuck: inspect git HEAD vs `pre_update_head`/`target_head` in `updater-state.json` before manual intervention; do not force-reset.

Manual one-shot Coordinator (`python -m tools.dev_coordinator`) remains available when process lock is not held.

## Activation boundary

Executor **did not** run `--enable-updater` or activate live systemd on the host.

Operator bootstrap (post-Architect review):

```bash
python3.10 scripts/install_dev_coordinator_runner.py \
  ...existing runner args... \
  --enable \
  --enable-updater
```

Until that one-time command, automatic transition advances do not occur.
