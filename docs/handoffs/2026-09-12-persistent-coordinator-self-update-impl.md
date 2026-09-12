# Handoff: Persistent Coordinator Self-Update (implementation)

Date: 2026-09-12

## Branch and SHAs

| Field | Value |
| --- | --- |
| Branch | `feat/002-persistent-coordinator-self-update-20260912` |
| Base SHA | `d2e13bfe93f11ded0cebb5bd1285cc92d00435ad` |
| Head SHA | *(pending Coordinator publication commit)* |

## Summary

Implemented fail-closed Coordinator tooling self-update per `specs/002-persistent-coordinator-self-update/*`:

- Strict `updater_config.py` with runner compatibility checks
- `MaintenanceGateLock` (shared/exclusive) and `UpdaterExclusionLock` in `locks.py`
- `updater.py` oneshot orchestration with injectable git/systemctl
- Runner cooperation via `scan_with_maintenance_gate` (shared lock before scan)
- systemd updater service + timer templates
- Installer extension with `--enable-updater` bootstrap flag
- Fake-only tests for git, locks, systemctl, installer, and state persistence

## Changed files

| Path | Change |
| --- | --- |
| `tools/dev_coordinator/updater_config.py` | new |
| `tools/dev_coordinator/updater.py` | new |
| `tools/dev_coordinator/locks.py` | extended |
| `tools/dev_coordinator/runner.py` | maintenance gate wrapper |
| `scripts/install_dev_coordinator_runner.py` | updater install + flags |
| `ops/systemd/ai-core-dev-coordinator-updater.service.in` | new |
| `ops/systemd/ai-core-dev-coordinator-updater.timer.in` | new |
| `tests/test_dev_coordinator_updater.py` | new |
| `tests/test_dev_coordinator_updater_install.py` | new |
| `docs/coordination/PERSISTENT_RUNNER.md` | self-update section |
| `specs/002-persistent-coordinator-self-update/tasks.md` | implementation status |
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

**Executor session:** shell commands were unavailable/rejected; tests were authored but not executed in this session. Do not treat as green until Coordinator verifies.

## Risks

| Risk | Mitigation |
| --- | --- |
| Runner stopped after failed ff-only with dirty/uncertain state | `HUMAN_REQUIRED`; no auto reset/clean; documented rollback |
| Manual one-shot races updater before process lock | Updater holds process lock in critical section; documented exceptional race |
| Runner starts under updater maintenance exclusive | Runner skips scans until exclusive released (no terminal candidate failures) |
| `coordinator_repo_root` drift between runner/updater configs | Parser rejects mismatch when both JSON files exist |
| Live timer enabled accidentally in dev | Tests use fake systemctl; Executor did not enable live systemd |

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
