---
coord_version: 1
state: EXECUTOR_READY
prompt_id: persistent-coordinator-self-update-impl-001
target_repo: kkobanenko/ai-core
target_branch: feat/002-persistent-coordinator-self-update-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/feat-002-persistent-coordinator-self-update-20260912
base_sha: d2e13bfe93f11ded0cebb5bd1285cc92d00435ad
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: tools/dev_coordinator/updater.py, tools/dev_coordinator/updater_config.py, tools/dev_coordinator/locks.py, tools/dev_coordinator/runner.py, scripts/install_dev_coordinator_runner.py, ops/systemd/ai-core-dev-coordinator-updater.service.in, ops/systemd/ai-core-dev-coordinator-updater.timer.in, tests/test_dev_coordinator_updater.py, tests/test_dev_coordinator_updater_install.py, tests/test_dev_coordinator_runner.py, tests/test_dev_coordinator_runner_install.py, docs/coordination/PERSISTENT_RUNNER.md, specs/002-persistent-coordinator-self-update/tasks.md, docs/handoffs/2026-09-12-persistent-coordinator-self-update-impl.md
required_paths: tools/dev_coordinator/updater.py, tools/dev_coordinator/updater_config.py, tools/dev_coordinator/locks.py, tools/dev_coordinator/runner.py, scripts/install_dev_coordinator_runner.py, ops/systemd/ai-core-dev-coordinator-updater.service.in, ops/systemd/ai-core-dev-coordinator-updater.timer.in, tests/test_dev_coordinator_updater.py, tests/test_dev_coordinator_updater_install.py, docs/coordination/PERSISTENT_RUNNER.md, specs/002-persistent-coordinator-self-update/tasks.md, docs/handoffs/2026-09-12-persistent-coordinator-self-update-impl.md
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "feat(coord): add safe persistent self-update"
---

# Implement Spec Kit package 002 — Persistent Coordinator self-update

Implement the reviewed authoritative spec at `specs/002-persistent-coordinator-self-update/*` as merged at base `d2e13bfe93f11ded0cebb5bd1285cc92d00435ad`.

This is tooling-plane only. Do not change `src/ai_core/**`, providers, runtime routing, consumers, platform-control, hosted CI, product deployment, releases, or tags.

## Required implementation

### 1. Strict updater configuration

Add `tools/dev_coordinator/updater_config.py` with strict JSON/config validation according to FR-001..FR-008 / tasks T001-T003.

At minimum validate:
- absolute existing Coordinator repo root;
- fixed non-empty transition branch, rejecting `main` / `master` and arbitrary empty ref;
- expected canonical origin identity/URL;
- runner service name;
- timer interval >= 30 seconds, default 60;
- absolute state dir;
- unknown keys rejected;
- compatibility with existing runner config coordinator root when both are supplied/loaded.

Keep config deterministic and stdlib-only.

### 2. Maintenance gate and lock ordering

Extend `tools/dev_coordinator/locks.py` with a maintenance gate using `fcntl.flock` on `${state_dir}/locks/coordinator-maintenance.lock`:
- runner mode: shared (`LOCK_SH`) non-blocking;
- updater mode: exclusive (`LOCK_EX`) non-blocking;
- explicit acquire/release, context-manager-safe;
- no lock-file deletion on release.

Updater exclusion lock must use `${state_dir}/locks/coordinator-updater.lock` and prevent concurrent updater instances.

Preserve existing `ProcessLock` behavior.

### 3. Runner cooperation

Minimally modify `tools/dev_coordinator/runner.py` so each persistent scan attempts maintenance SHARED before calling `scan_repositories` and holds it for the entire scan/candidate processing/delegated `run_once` sequence.

If maintenance shared cannot be acquired because updater holds exclusive:
- skip that poll cycle;
- do not read/process/terminalize any candidate;
- log an informational/diagnosable maintenance skip;
- retry on normal cadence.

`--once` should follow the same maintenance rule and return a clear skipped summary rather than mutating candidate state.

Do not change bridge authority, claim semantics, discovery namespace, publication rules, or max executor behavior.

### 4. Updater orchestration

Add `tools/dev_coordinator/updater.py` with injectable git/systemctl/lock runners for tests and `--once` / `--status` CLI.

Required deterministic sequence for an update attempt:

1. acquire updater exclusion lock; if unavailable -> `SKIPPED/updater_busy`;
2. `git fetch origin` only;
3. read local and remote reviewed transition heads; equal -> `NOOP`, zero runner stop/start;
4. acquire maintenance EXCLUSIVE non-blocking; unavailable -> `SKIPPED/maintenance_held`, zero stop/merge/start;
5. acquire existing Coordinator `ProcessLock` and HOLD it; unavailable -> release maintenance, `SKIPPED/process_lock_held`;
6. while both locks held, verify correct canonical repo/origin, exact configured transition branch, clean checkout, remote is a fast-forward descendant;
7. `systemctl --user stop <runner-service>`;
8. execute exactly strict `git merge --ff-only origin/<transition-branch>` as the only git mutation;
9. verify resulting HEAD == fetched remote head and worktree remains clean;
10. on success, `systemctl --user start <runner-service>` exactly once;
11. release locks in reverse order and persist state.

Forbidden mutation commands: reset, clean, checkout branch switching, rebase, stash, pull, force fetch/merge, branch deletion, auto conflict repair.

Manual one-shot Coordinator need not acquire maintenance gate in this feature, but updater holding ProcessLock must prevent it from executing during the critical section.

### 5. Post-stop failure behavior

If ff-only unexpectedly fails after runner stop:
- compare current HEAD/worktree against the pre-stop verified clean snapshot;
- if provably unchanged + clean: start previous runner once, record `FAIL_CLOSED/ff_refused_recoverable`; no immediate retry loop;
- if changed, dirty, or uncertain: do not start runner; record `HUMAN_REQUIRED/ff_refused` (or equivalent explicit fail-closed status);
- never reset/clean/force to recover.

If `systemctl stop` itself fails, do not mutate git.
If successful git update occurs but runner start fails, record a fail-closed/human-required service state; do not loop restart.

### 6. State and observability

Persist `${state_dir}/updater-state.json` atomically. Include:
- local_head;
- remote_head when known;
- last_attempt_at;
- last_result (`NOOP`, `SUCCESS`, `SKIPPED`, `FAIL_CLOSED`, `HUMAN_REQUIRED` as appropriate);
- reason;
- last_success_head;
- last_runner_restart_at.

No secrets/prompt bodies/credentials in state or logs.
`--status` must be read-only and machine-readable with `--json` if consistent with current tooling conventions.

### 7. systemd and installer

Add:
- `ops/systemd/ai-core-dev-coordinator-updater.service.in` as Type=oneshot invoking updater `--once`;
- `ops/systemd/ai-core-dev-coordinator-updater.timer.in` with default ~60s cadence, not faster than 30s.

Extend `scripts/install_dev_coordinator_runner.py` idempotently:
- keep existing runner install/config behavior compatible;
- write updater config + service + timer units;
- add explicit `--enable-updater` activation flag;
- without flag, write updater artifacts only;
- with flag, `daemon-reload` and enable/start timer as required;
- no live updater activation from tests.

There remains one final explicit operator bootstrap after Architect review/merge. After that, future reviewed transition merges must advance/restart automatically.

### 8. Tests

Add fake-only tests covering all tasks T003/T009/T015/T019/T025, especially:
- already current -> NOOP, no stop/start;
- clean ff-only -> stop once, merge ff-only once, start once;
- dirty/diverged/wrong branch/wrong origin/fetch failure -> no git mutation, no stop/start;
- runner holds maintenance shared -> updater SKIP, zero stop/merge/start;
- updater holds maintenance exclusive -> runner scan skips and terminalizes no candidate;
- updater holds Coordinator ProcessLock throughout critical stop+merge+start;
- concurrent fake harness validates documented lock ordering / no deadlock;
- ff failure proven unchanged+clean -> old runner restored once + FAIL_CLOSED;
- ff failure uncertain/changed -> runner remains stopped + HUMAN_REQUIRED;
- systemctl stop failure -> no merge;
- start failure after successful merge -> explicit fail-closed/human-required state;
- updater state/status persistence;
- installer first install and idempotent reinstall, generated units/config, enable-updater calls, runner compatibility.

Preserve/fix existing persistent runner tests; no substring-style flag checks.

If shell is available, run:
`PYTHONPATH=. python3.10 -m pytest -q tests/test_dev_coordinator_updater.py tests/test_dev_coordinator_updater_install.py tests/test_dev_coordinator_runner.py tests/test_dev_coordinator_runner_install.py tests/test_dev_coordinator.py`
and `git diff --check d2e13bfe93f11ded0cebb5bd1285cc92d00435ad HEAD`.
If shell is unavailable, state that explicitly; never invent green results.

### 9. Docs and handoff

Update `docs/coordination/PERSISTENT_RUNNER.md` with self-update architecture, one-time bootstrap, status and rollback.
Mark completed implementation tasks accurately in `specs/002-persistent-coordinator-self-update/tasks.md`.
Create `docs/handoffs/2026-09-12-persistent-coordinator-self-update-impl.md` with exact base, changed files, tests actually run, risks, rollback, and final activation boundary.

## Hard boundaries

Do not activate live updater/systemd on the host from Executor.
Do not run hosted CI.
Do not create PRs, merge, tag, release, deploy, delete branches/worktrees, or mutate platform-control.
Do not modify `.specify/memory/constitution.md`.
Do not commit/push yourself; Coordinator owns exact-path publication and remote verification.

Finish with concise Executor summary and stop.
