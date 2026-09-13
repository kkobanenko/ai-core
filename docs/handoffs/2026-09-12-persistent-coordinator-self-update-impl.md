# Handoff: Persistent Coordinator Self-Update (implementation)

Date: 2026-09-12

## Branch and SHAs

| Field | Value |
| --- | --- |
| Branch | `feat/002-persistent-coordinator-self-update-20260912` |
| Base SHA | `d2e13bfe93f11ded0cebb5bd1285cc92d00435ad` |
| Head SHA | *(pending Coordinator publication commit after review-fix 4)* |
| Review-fix 1 base | `59973911dd4e6186f66aabbf65909cf9a6c95858` |
| Review-fix 2 base | `319524d62ffd769d9056986a61a3cfd4e02f8aed` |
| Review-fix 3 base | `8317cb4aabab354d4f9ff3beeb8140658aeea5e8` |
| Review-fix 4 base | `b26de225a7d7d7c24bc7ef182e1eea57908ab896` |

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

### Architect review-fix 3 (recovery/concurrency races)

- **Immutable outcomes on lock skip**: pending/legacy recovery lock-contention paths construct new `UpdateOutcome` instead of mutating frozen instances.
- **Exclusion lock ordering**: `UpdaterExclusionLock` acquired before `load_updater_state_strict`; `updater_busy` returns without reading or writing `updater-state.json`.
- **ff-only refusal + runner restore failure**: unchanged/clean worktree + failed `systemctl start` → `HUMAN_REQUIRED / ff_refused_runner_restore_failed`, `pending_update` preserved; next tick performs bounded start-only recovery via pending marker (no merge).
- **Strict durable state**: `load_updater_state_strict` fails closed on corrupt JSON or unsupported version; present-but-invalid `pending_update` → `HUMAN_REQUIRED / pending_update_invalid` with no fetch/systemctl/git mutation and no state overwrite; `--status` exposes `state_load_error` when strict load fails.
- Added `TestUpdaterReviewFix3` and `test_exclusion_busy_does_not_alter_state` regression tests.

### Architect review-fix 4 (restart-safe updater bootstrap)

- **`--enable-updater` activation contract**: deterministic `daemon-reload` → runner `enable` → explicit `restart` → updater timer `enable --now`. Never enables timer unless runner restart succeeds on the installed unit.
- **`--enable-updater` implies runner activation** in the same installer transaction; combining with `--enable` uses the updater bootstrap path (one restart, no redundant runner `enable --now`).
- **Fail-closed ordering**: `daemon-reload` or runner restart failure prevents timer enable; timer enable failure surfaces installer error (runner may remain on new code).
- Installer tests inject fake `systemctl_runner`; no live systemd activation from Executor.

## Changed files

| Path | Change |
| --- | --- |
| `tools/dev_coordinator/updater_config.py` | new |
| `tools/dev_coordinator/updater.py` | new; review-fix 1 + 2 + 3 |
| `tools/dev_coordinator/locks.py` | extended |
| `tools/dev_coordinator/runner.py` | maintenance gate wrapper |
| `scripts/install_dev_coordinator_runner.py` | updater install + restart-safe bootstrap |
| `ops/systemd/ai-core-dev-coordinator-updater.service.in` | new |
| `ops/systemd/ai-core-dev-coordinator-updater.timer.in` | new |
| `tests/test_dev_coordinator_updater.py` | new; review-fix 1 + 2 + 3 tests |
| `tests/test_dev_coordinator_updater_install.py` | new; review-fix 4 bootstrap ordering tests |
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

**Review-fix 3 gate (Coordinator / operator should run locally):**

```bash
PYTHONPATH=. python3.10 -m pytest -q \
  tests/test_dev_coordinator_updater.py \
  tests/test_dev_coordinator_updater_install.py \
  tests/test_dev_coordinator_runner.py \
  tests/test_dev_coordinator_runner_install.py \
  tests/test_dev_coordinator.py

git diff --check 8317cb4aabab354d4f9ff3beeb8140658aeea5e8 HEAD
```

**Review-fix 4 gate (Coordinator / operator should run locally):**

```bash
PYTHONPATH=. python3.10 -m pytest -q \
  tests/test_dev_coordinator_updater_install.py \
  tests/test_dev_coordinator_runner_install.py

git diff --check b26de225a7d7d7c24bc7ef182e1eea57908ab896 HEAD
```

**Executor session (review-fix 4):** shell commands unavailable/rejected; tests authored but not executed. Coordinator must verify before merge.

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
| `updater_busy` overwrites lock-owner state (review-fix 3) | Exclusion acquired before state load; busy path is read/write-free |
| Corrupt `updater-state.json` silently reset (review-fix 3) | Strict load fails closed; status exposes `state_load_error` |
| ff refusal + failed runner restore loses marker (review-fix 3) | `pending_update` preserved; next tick start-only recovery |
| Old runner still active after unit rewrite (review-fix 4) | `--enable-updater` requires explicit restart before timer enable |
| Timer enabled while runner on stale code (review-fix 4) | Fail-closed: restart failure blocks timer enable |

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
