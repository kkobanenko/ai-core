# Tasks: Persistent Coordinator Self-Update

**Feature**: `002-persistent-coordinator-self-update`

**Authority**: `spec.md` + `plan.md`; this file is specification-only — implementation tasks are for the follow-on package.

**Package type**: SPEC-ONLY (no production code in this branch)

## Phase 0 — Specification (this package)

- [x] **T000** Author `spec.md` covering authority, git safety, lock coordination, supervision, installer bootstrap, observability, testing, and rollback.
- [x] **T000a** Author `research.md` with architecture decisions (separate updater service, ff-only, maintenance gate, deterministic lock ordering).
- [x] **T000f** Architect review fix: close self-update lock race — maintenance gate shared/exclusive, post-stop failure policy, explicit test matrix (FR-035).
- [x] **T000b** Author `plan.md` with technical context, structure, validation strategy, and implementation boundaries.
- [x] **T000c** Author `tasks.md` (this file) with dependency-ordered implementation tasks for the next package.
- [x] **T000d** Author `quickstart.md` describing bootstrap and normal operation.
- [x] **T000e** Author handoff `docs/handoffs/2026-09-12-persistent-coordinator-self-update-spec.md`.

## Phase 1 — Updater config and precondition checks (implementation package)

- [x] **T001** Add `tools/dev_coordinator/updater_config.py` with strict JSON parsing for coordinator repo root, transition branch, expected origin URL, runner service name, timer interval, state dir.
- [x] **T002** Reject unknown keys, relative paths, empty branch/origin, interval below minimum (30s), and coordinator root mismatch vs existing runner config when both present.
- [x] **T003** Add unit tests for valid config and every fail-closed config case.

## Phase 2 — Git precondition and ff-only advance

- [x] **T004** Add `tools/dev_coordinator/updater.py` with injectable git runner for testability.
- [x] **T005** Implement `git fetch origin` only; no other remotes or fetch flags.
- [x] **T006** Implement precondition checks: canonical repo path, correct branch, clean worktree, expected origin URL (normalized), local behind remote.
- [x] **T007** Implement strict `git merge --ff-only origin/<transition-branch>` as the only mutation; verify post-merge HEAD equals remote.
- [x] **T008** Fail closed on dirty, diverged, wrong branch, wrong origin, fetch failure, or non-ff merge without reset/clean/checkout/rebase/stash.
- [x] **T009** Add fake-git tests for NOOP (already current), success ff-only, dirty refusal, diverged refusal, wrong branch/origin refusal.

## Phase 3 — Maintenance gate, lock coordination, and runner lifecycle

- [x] **T010** Add `MaintenanceGateLock` to `tools/dev_coordinator/locks.py` with shared (runner) and exclusive (updater) non-blocking acquisition on `${state_dir}/locks/coordinator-maintenance.lock`.
- [x] **T010a** Extend `tools/dev_coordinator/runner.py`: acquire maintenance shared before each scan; hold through candidate processing and delegated `run_once`; skip scan without terminalizing candidates when exclusive held; release shared after scan cycle.
- [x] **T011** Add updater exclusion lock `${state_dir}/locks/coordinator-updater.lock` preventing concurrent updater runs.
- [x] **T012** Implement deterministic updater sequence: exclusion → fetch → NOOP check (no runner stop) → maintenance(exclusive) → Coordinator process lock (hold) → preconditions → runner stop → ff-only → conditional runner start → release locks reverse order.
- [x] **T013** On ff-only failure after runner stop: verify pre-update HEAD/worktree snapshot; if proven unchanged+clean, MAY restore runner once + `FAIL_CLOSED`; else `HUMAN_REQUIRED`, runner stopped; never reset/clean/force; never tight restart loop.
- [x] **T014** Inject fake systemctl; successful head change triggers exactly one runner stop + one start; NOOP/SKIP/FAIL_CLOSED (pre-stop) trigger zero restarts.
- [x] **T015** Add fake-lock tests per FR-035:
  - runner holds maintenance shared → updater SKIP, zero stop/merge/start;
  - updater holds maintenance exclusive → runner skips scan, no terminal candidate failures;
  - updater holds Coordinator process lock during stop+merge+start;
  - concurrent fake harness: no deadlock with documented lock ordering;
  - ff failure + proven unchanged clean → runner restored once, `FAIL_CLOSED`;
  - ff failure + uncertain/changed state → runner stopped, `HUMAN_REQUIRED`;
  - no-op path never stops runner.

## Phase 4 — State, CLI, and observability

- [x] **T016** Persist `updater-state.json` atomically with local head, remote head, last attempt, result, reason, last success head, last runner restart timestamp.
- [x] **T017** Add `--once` and `--status` CLI entry points; status is read-only.
- [x] **T018** Emit structured journal-friendly log lines; never log secrets.
- [x] **T019** Add tests for state persistence across attempts and status command output.

## Phase 5 — systemd units and installer extension

- [x] **T020** Add `ops/systemd/ai-core-dev-coordinator-updater.service.in` (Type=oneshot, invokes updater `--once`).
- [x] **T021** Add `ops/systemd/ai-core-dev-coordinator-updater.timer.in` with conservative default interval (~60s) and documented configurability.
- [x] **T022** Extend `scripts/install_dev_coordinator_runner.py` to write updater config/units idempotently.
- [x] **T023** Add `--enable-updater` flag: `daemon-reload`, enable timer (and required oneshot wiring); without flag, write-only install.
- [x] **T024** Ensure tests inject/fake systemctl; implementation tests MUST NOT enable live workstation timer.
- [x] **T025** Add installer tests: first install, idempotent reinstall, invalid paths, generated unit contents, runner config compatibility.

## Phase 6 — Documentation and compatibility

- [x] **T026** Extend `docs/coordination/PERSISTENT_RUNNER.md` with self-update architecture, bootstrap boundary, status commands, and rollback.
- [x] **T027** Do not change `src/ai_core/**`, provider/runtime/tracing APIs, platform-control contracts, or consumer repositories.
- [x] **T028** Do not modify `.specify/memory/constitution.md`.

## Phase 7 — Verification (implementation package)

- [ ] **T029** Run focused updater + installer tests (`test_dev_coordinator_updater*.py`). *(Executor: shell unavailable in session; tests written, not executed here.)*
- [ ] **T030** Run full existing runner + coordinator test suites to prove no regression. *(Executor: shell unavailable in session.)*
- [ ] **T031** Run `git diff --check` against implementation base. *(Executor: shell unavailable in session.)*
- [ ] **T032** Manual `--once` smoke against harmless test clone (no live timer enable in test/CI).
- [x] **T033** Produce implementation handoff with branch, base/head SHAs, tests, risks, rollback.

## Phase 8 — Architect review and operator bootstrap

- [x] **T033a** Architect review-fix 1: sticky post-stop recovery — `local==remote` must not downgrade unresolved `HUMAN_REQUIRED` to `NOOP`; bounded `runner_start_failed` recovery under locks; regression tests for consecutive attempts.
- [x] **T033b** Architect review-fix 2: pre-fetch authority gate (no fetch on wrong origin/branch/dirty); durable `pending_update` marker before stop; crash-boundary recovery by HEAD comparison; sticky recovery survives transient `SKIPPED`; regression tests for all 12 cases.
- [ ] **T034** Architect exact-head review before implementation merge.
- [ ] **T035** Merge only after required local tests are green; hosted CI not used as iteration mechanism.
- [ ] **T036** Operator runs one explicit install command with `--enable-updater` after reviewed code is available locally (bootstrap boundary).
- [ ] **T037** Verify automatic advance on next reviewed transition merge without per-update terminal commands.
- [ ] **T038** Confirm rollback: disable updater timer leaves runner usable; manual one-shot Coordinator remains available.
