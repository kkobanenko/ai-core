# Implementation Plan: Persistent Coordinator Self-Update

**Branch**: `spec/002-persistent-coordinator-self-update-20260912` | **Date**: 2026-09-12 | **Spec**: `specs/002-persistent-coordinator-self-update/spec.md`

**Input**: Feature specification from `/specs/002-persistent-coordinator-self-update/spec.md`

## Summary

Add a conservative, fail-closed self-update path for the Coordinator tooling checkout and persistent runner. A separate `systemd --user` timer invokes an oneshot updater that: fetches `origin`, verifies canonical repo/branch/clean/ff-only preconditions, respects the Coordinator process lock, stops the runner only when needed, fast-forwards the configured transition branch, and restarts the runner exactly once on successful head change. Extend the existing idempotent installer with a one-time updater activation boundary. Spec-only in this package; implementation follows in a separate package.

## Technical Context

**Language/Version**: Python 3.10

**Primary Dependencies**: Python stdlib; existing `tools.dev_coordinator` (`ProcessLock`, paths); git CLI; systemd user manager; existing runner installer/units

**Storage**: JSON updater config (colocated with runner config namespace) and JSON updater state under XDG state dir

**Testing**: pytest with fake git, fake systemctl, fake flock; no live systemd mutation

**Target Platform**: User workstation, Linux with systemd user services

**Project Type**: developer automation CLI/service extension

**Performance Goals**: detect and apply a new transition head within ~2 minutes at default 60s timer; negligible idle cost; no restart loops

**Constraints**: fail closed; ff-only; no force/reset/clean/rebase/stash; no inline runner self-mutation; no secrets in state; no hosted CI; no `src/ai_core/**` changes; coordinate with existing `coordinator.lock`

**Scale/Scope**: single operator workstation; single canonical Coordinator checkout; transition branch `chore/coordinator-transition-v0.1-20260911`

## Constitution Check

`.specify/memory/constitution.md` is unratified. Operative gates: `AGENTS.md`, platform-control, `docs/coordination/TRANSITION_PLAN.md`.

Pre-design gates:

- PASS — deterministic Python owns update decisions; LLM/Executor gains no authority.
- PASS — update source is only Architect-reviewed transition branch merges on GitHub.
- PASS — existing Coordinator claim/process-lock semantics preserved; updater skips when lock held.
- PASS — tooling-plane only; ai-core runtime/provider/tracing untouched.
- PASS — failures fail-closed with diagnosable state; no auto-repair of dirty/diverged git.
- PASS — bootstrap requires explicit one-time operator activation.

Post-design re-check: no complexity exception required.

## Architecture

### Control flow

```text
Architect merge → transition branch on GitHub
                         ↓
        updater.timer (~60s, configurable)
                         ↓
        updater.service (oneshot)
                         ↓
   acquire updater exclusion lock
                         ↓
        git fetch origin (Coordinator checkout)
                         ↓
     remote == local HEAD? → NOOP (no runner restart)
                         ↓
   process lock free + clean + correct branch/origin?
         no → SKIP/FAIL_CLOSED (retry later)
                         ↓
        stop runner.service
                         ↓
        re-verify lock + ff-only mergeability
                         ↓
   git merge --ff-only origin/<transition-branch>
                         ↓
   HEAD changed? → start runner.service once
                         ↓
        persist updater state + journal log
```

### Authority model

| Input | Allowed | Forbidden |
| --- | --- | --- |
| `origin/<configured-transition-branch>` after Architect merge | fast-forward source | — |
| `main`, `master`, feature branches | — | any auto tracking |
| Arbitrary ref from prompt/env | — | yes |
| PR auto-merge | — | yes |

Configuration is operator/installer supplied only. Remote bridge prompts cannot retarget the updater.

### Git safety checks (all must pass before merge)

1. `coordinator_repo_root` resolves to the configured canonical path.
2. `git rev-parse --abbrev-ref HEAD` equals configured transition branch.
3. `git status --porcelain` is empty.
4. `git remote get-url origin` matches expected canonical URL (normalized compare).
5. `git merge-base --is-ancestor HEAD origin/<branch>` and remote is strictly ahead (or equal → no-op earlier).
6. `git merge --ff-only origin/<branch>` is the only mutation permitted.

Forbidden commands: `reset`, `clean`, `checkout` (branch switch), `rebase`, `stash`, `pull`, force fetch, remote other than `origin`.

### Lock coordination

Reuse `tools.dev_coordinator.locks.ProcessLock` against `${state_dir}/locks/coordinator.lock` in **non-blocking probe** mode before runner stop.

Updater exclusion lock: `${state_dir}/locks/coordinator-updater.lock`, held for entire oneshot execution.

Race policy:

- If process lock becomes held after runner stop but before merge: abort merge attempt, leave runner stopped, record `lock_held_after_stop` for operator attention (fail-closed).
- If merge fails after runner stop: do not start runner automatically in a loop; record `ff_refused`; operator uses documented recovery.

### Service supervision

| Unit | Type | Role |
| --- | --- | --- |
| `ai-core-dev-coordinator-runner.service` | long-running | unchanged package polling |
| `ai-core-dev-coordinator-updater.service` | oneshot | single update attempt |
| `ai-core-dev-coordinator-updater.timer` | timer | triggers oneshot ~60s |

Timer MUST NOT be faster than 30s in production defaults without documented justification. Implementation tests MUST NOT enable live timer.

Restart policy:

- `SUCCESS` with head change → exactly one `systemctl --user start` on runner.
- `NOOP`, `SKIPPED`, `FAIL_CLOSED` (pre-stop) → no runner stop/start.
- `FAIL_CLOSED` after stop → no auto-start loop; status exposes recovery commands.

### Configuration (proposed)

Extension to installer-generated config, e.g. `~/.config/ai-core-dev-coordinator/updater.json`:

```json
{
  "coordinator_repo_root": "/absolute/path/to/coordinator-checkout",
  "transition_branch": "chore/coordinator-transition-v0.1-20260911",
  "expected_origin_url": "https://github.com/kkobanenko/ai-core.git",
  "runner_service": "ai-core-dev-coordinator-runner.service",
  "timer_interval_seconds": 60,
  "state_dir": "/home/operator/.local/state/ai-core-dev-coordinator"
}
```

Parser rejects unknown keys, relative paths, empty branch, intervals < 30, and mismatch with runner `coordinator_repo_root` when both files exist.

### Installer / activation

Extend `scripts/install_dev_coordinator_runner.py`:

- write updater unit + timer templates under `ops/systemd/`
- `--enable-updater` performs `daemon-reload`, `enable --now` timer (and oneshot wiring)
- without flag: write units only (same pattern as runner `--enable`)
- idempotent reinstall updates unit contents and config without duplicating services

**Bootstrap boundary**: until operator runs post-review install with `--enable-updater`, timer is inactive and no automatic git advance occurs. This is the last routine terminal activation for transition maintenance.

### Observability

- State file: `${state_dir}/updater-state.json` (atomic write)
- CLI: `python3.10 -m tools.dev_coordinator.updater --status`
- Journal: `journalctl --user -u ai-core-dev-coordinator-updater.service`

Fields: `local_head`, `remote_head`, `last_attempt_at`, `last_result`, `reason`, `last_success_head`, `last_runner_restart_at`.

No secrets, prompt bodies, or credentials.

## Project Structure

### Documentation (this feature)

```text
specs/002-persistent-coordinator-self-update/
├── spec.md
├── plan.md
├── research.md
├── quickstart.md
└── tasks.md
```

### Source Code (implementation package — not in this spec-only commit)

```text
tools/dev_coordinator/
├── updater.py              # oneshot update orchestration
├── updater_config.py       # strict JSON parsing
└── locks.py                # reuse ProcessLock; optional thin wrapper

scripts/
└── install_dev_coordinator_runner.py   # extended with updater units/flags

ops/systemd/
├── ai-core-dev-coordinator-updater.service.in
└── ai-core-dev-coordinator-updater.timer.in

tests/
├── test_dev_coordinator_updater.py
└── test_dev_coordinator_updater_install.py

docs/coordination/
└── PERSISTENT_RUNNER.md    # add self-update section (implementation package)
```

**Structure Decision**: Keep updater adjacent to runner/coordinator modules; do not fold into `src/ai_core` or the runner poll loop.

## Validation Strategy

1. Config parser tests: valid config, unknown keys, relative paths, interval bounds, origin/branch empty.
2. Fake-git: already-current → NOOP, no systemctl start.
3. Fake-git: clean ff-only advance → merge called once, runner stop then start once.
4. Fake-git: dirty tree → FAIL_CLOSED, no stop/start.
5. Fake-git: diverged → FAIL_CLOSED, no merge.
6. Fake-git: wrong branch / wrong origin → FAIL_CLOSED.
7. Fake-lock: process lock held → SKIP, no stop/start.
8. Fake-lock: lock appears after stop → FAIL_CLOSED, runner not restarted automatically.
9. Fake-systemctl: failure path does not loop restart.
10. Installer idempotence with injected systemctl.
11. Regression: full existing runner + coordinator test suites remain green.
12. Manual smoke (implementation package): `--once` updater dry run against test clone; no live timer in CI.

## Rollback

**Before updater activation**: revert implementation; runner unaffected.

**After activation**:

```bash
systemctl --user disable --now ai-core-dev-coordinator-updater.timer
systemctl --user disable --now ai-core-dev-coordinator-updater.service
```

Runner continues on last known-good checkout. Disable runner separately if needed. Manual one-shot Coordinator always available.

## Implementation package boundaries (next)

| In scope (implementation) | Out of scope |
| --- | --- |
| updater module, units, installer extension, tests, docs section | `src/ai_core/**` |
| fake harness tests | hosted CI |
| `PERSISTENT_RUNNER.md` self-update section | platform-control contract changes |
| local smoke `--once` | live timer enable in tests |
| handoff for implementation merge | PR creation by Executor |

Suggested implementation branch naming: `feat/002-persistent-coordinator-self-update-20260912` after spec merge.

## Complexity Tracking

No constitution violation or required complexity exception identified.
