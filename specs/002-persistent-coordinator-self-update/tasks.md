# Tasks: Persistent Coordinator Self-Update

**Feature**: `002-persistent-coordinator-self-update`

**Authority**: `spec.md` + `plan.md`; this file is specification-only — implementation tasks are for the follow-on package.

**Package type**: SPEC-ONLY (no production code in this branch)

## Phase 0 — Specification (this package)

- [x] **T000** Author `spec.md` covering authority, git safety, lock coordination, supervision, installer bootstrap, observability, testing, and rollback.
- [x] **T000a** Author `research.md` with architecture decisions (separate updater service, ff-only, lock reuse, race-safe sequence).
- [x] **T000b** Author `plan.md` with technical context, structure, validation strategy, and implementation boundaries.
- [x] **T000c** Author `tasks.md` (this file) with dependency-ordered implementation tasks for the next package.
- [x] **T000d** Author `quickstart.md` describing bootstrap and normal operation.
- [x] **T000e** Author handoff `docs/handoffs/2026-09-12-persistent-coordinator-self-update-spec.md`.

## Phase 1 — Updater config and precondition checks (implementation package)

- [ ] **T001** Add `tools/dev_coordinator/updater_config.py` with strict JSON parsing for coordinator repo root, transition branch, expected origin URL, runner service name, timer interval, state dir.
- [ ] **T002** Reject unknown keys, relative paths, empty branch/origin, interval below minimum (30s), and coordinator root mismatch vs existing runner config when both present.
- [ ] **T003** Add unit tests for valid config and every fail-closed config case.

## Phase 2 — Git precondition and ff-only advance

- [ ] **T004** Add `tools/dev_coordinator/updater.py` with injectable git runner for testability.
- [ ] **T005** Implement `git fetch origin` only; no other remotes or fetch flags.
- [ ] **T006** Implement precondition checks: canonical repo path, correct branch, clean worktree, expected origin URL (normalized), local behind remote.
- [ ] **T007** Implement strict `git merge --ff-only origin/<transition-branch>` as the only mutation; verify post-merge HEAD equals remote.
- [ ] **T008** Fail closed on dirty, diverged, wrong branch, wrong origin, fetch failure, or non-ff merge without reset/clean/checkout/rebase/stash.
- [ ] **T009** Add fake-git tests for NOOP (already current), success ff-only, dirty refusal, diverged refusal, wrong branch/origin refusal.

## Phase 3 — Lock coordination and runner lifecycle

- [ ] **T010** Reuse `ProcessLock` non-blocking probe on `${state_dir}/locks/coordinator.lock`; skip with reason when held.
- [ ] **T011** Add updater exclusion lock `${state_dir}/locks/coordinator-updater.lock` preventing concurrent updater runs.
- [ ] **T012** Implement race-safe sequence: exclusion lock → fetch → NOOP check → process lock probe → preconditions → runner stop → re-verify lock + preconditions → ff-only → conditional runner start.
- [ ] **T013** On ff-only failure after runner stop: record fail-closed state, do not enter restart loop; document recovery in status output.
- [ ] **T014** Inject fake systemctl; successful head change triggers exactly one runner stop + one start; NOOP/SKIP/FAIL_CLOSED (pre-stop) trigger zero restarts.
- [ ] **T015** Add fake-lock tests: active Coordinator lock → SKIP; lock after stop → FAIL_CLOSED without auto-restart loop.

## Phase 4 — State, CLI, and observability

- [ ] **T016** Persist `updater-state.json` atomically with local head, remote head, last attempt, result, reason, last success head, last runner restart timestamp.
- [ ] **T017** Add `--once` and `--status` CLI entry points; status is read-only.
- [ ] **T018** Emit structured journal-friendly log lines; never log secrets.
- [ ] **T019** Add tests for state persistence across attempts and status command output.

## Phase 5 — systemd units and installer extension

- [ ] **T020** Add `ops/systemd/ai-core-dev-coordinator-updater.service.in` (Type=oneshot, invokes updater `--once`).
- [ ] **T021** Add `ops/systemd/ai-core-dev-coordinator-updater.timer.in` with conservative default interval (~60s) and documented configurability.
- [ ] **T022** Extend `scripts/install_dev_coordinator_runner.py` to write updater config/units idempotently.
- [ ] **T023** Add `--enable-updater` flag: `daemon-reload`, enable timer (and required oneshot wiring); without flag, write-only install.
- [ ] **T024** Ensure tests inject/fake systemctl; implementation tests MUST NOT enable live workstation timer.
- [ ] **T025** Add installer tests: first install, idempotent reinstall, invalid paths, generated unit contents, runner config compatibility.

## Phase 6 — Documentation and compatibility

- [ ] **T026** Extend `docs/coordination/PERSISTENT_RUNNER.md` with self-update architecture, bootstrap boundary, status commands, and rollback.
- [ ] **T027** Do not change `src/ai_core/**`, provider/runtime/tracing APIs, platform-control contracts, or consumer repositories.
- [ ] **T028** Do not modify `.specify/memory/constitution.md`.

## Phase 7 — Verification (implementation package)

- [ ] **T029** Run focused updater + installer tests (`test_dev_coordinator_updater*.py`).
- [ ] **T030** Run full existing runner + coordinator test suites to prove no regression.
- [ ] **T031** Run `git diff --check` against implementation base.
- [ ] **T032** Manual `--once` smoke against harmless test clone (no live timer enable in test/CI).
- [ ] **T033** Produce implementation handoff with branch, base/head SHAs, tests, risks, rollback.

## Phase 8 — Architect review and operator bootstrap

- [ ] **T034** Architect exact-head review before implementation merge.
- [ ] **T035** Merge only after required local tests are green; hosted CI not used as iteration mechanism.
- [ ] **T036** Operator runs one explicit install command with `--enable-updater` after reviewed code is available locally (bootstrap boundary).
- [ ] **T037** Verify automatic advance on next reviewed transition merge without per-update terminal commands.
- [ ] **T038** Confirm rollback: disable updater timer leaves runner usable; manual one-shot Coordinator remains available.
