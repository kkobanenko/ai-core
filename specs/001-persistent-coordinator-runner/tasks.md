# Tasks: Persistent Coordinator Runner

**Feature**: `001-persistent-coordinator-runner`

**Authority**: `spec.md` + `plan.md`; bridge prompt is execution transport only.

## Phase 1 — Config and safety foundation

- [ ] **T001** Add `tools/dev_coordinator/runner_config.py` with strict stdlib JSON parsing for poll interval, Coordinator root, managed worktree root, agent path, bridge prefix and repository allowlist.
- [ ] **T002** Reject unknown config keys, relative paths, duplicate repository paths, missing configured clones, unsupported bridge prefix, invalid poll intervals and empty allowlist.
- [ ] **T003** Add tests for valid config and every fail-closed config case.

## Phase 2 — Managed worktree preparation

- [ ] **T004** Add `tools/dev_coordinator/managed_worktrees.py` with canonical containment checks under one managed root.
- [ ] **T005** Implement bridge-worktree prepare/reuse with exact repo/branch/SHA/clean checks and no force.
- [ ] **T006** Implement executor-worktree prepare/reuse with exact target repo/branch/base SHA/clean checks.
- [ ] **T007** Fail closed if a required branch is checked out outside the managed root, if a path is inconsistent, or target is `main`/`master`.
- [ ] **T008** Add tests for create, safe reuse, stale/mismatched worktree, outside-root path, branch collision and missing remote ref.

## Phase 3 — Remote discovery and persistent scheduling

- [ ] **T009** Add `tools/dev_coordinator/runner.py` with `--once`, persistent-loop and `--status` modes.
- [ ] **T010** Fetch only configured repositories and enumerate only `refs/remotes/origin/coord/bridge/*`.
- [ ] **T011** Read prompt content from the exact remote bridge ref and parse with existing `parse_next_prompt` before worktree creation.
- [ ] **T012** Ignore non-ready states; fail closed on malformed ready candidates; require target repo allowlist and managed target-worktree path.
- [ ] **T013** Process candidates serially and delegate execution to existing one-shot Coordinator path instead of reimplementing claim/publication logic.
- [ ] **T014** Persist terminal `(bridge repo, branch, SHA)` results atomically in runner state and skip unchanged terminal candidates after restart.
- [ ] **T015** Preserve Coordinator exactly-once claims; do not implement automatic claim reclaim.
- [ ] **T016** Keep service alive across fetch/network errors and record structured diagnostics for later polling.
- [ ] **T017** Add tests proving no discovery outside `coord/bridge/*`, serial execution, restart idempotency, changed-SHA reconsideration, network error recovery and zero duplicate launches.

## Phase 4 — Installation and service lifecycle

- [ ] **T018** Add `ops/systemd/ai-core-dev-coordinator-runner.service.in` with user-service restart behavior and no privileged execution.
- [ ] **T019** Add `scripts/install_dev_coordinator_runner.py` that resolves/writes absolute paths, writes config/unit idempotently and supports explicit `--enable`.
- [ ] **T020** Ensure tests can inject/fake systemctl; implementation tests MUST NOT enable the real workstation service.
- [ ] **T021** Add installer tests for first install, idempotent reinstall, invalid agent/Python/repo paths and generated unit contents.

## Phase 5 — Documentation and compatibility

- [ ] **T022** Add `docs/coordination/PERSISTENT_RUNNER.md` describing architecture, safety boundaries, `coord/bridge/*` convention, status/logging, activation and rollback.
- [ ] **T023** Update `docs/coordination/TRANSITION_PLAN.md` to record that the first Spec Kit-native package is this runner feature and that old bridge is now transport rather than specification authority for new packages.
- [ ] **T024** Do not change `src/ai_core/**`, provider/runtime/tracing APIs, dependency set, old PR #3/#4/#5, or consumer repositories.

## Phase 6 — Verification

- [ ] **T025** Run focused new runner/installer tests.
- [ ] **T026** Run the complete existing Coordinator test suite to prove claim/safety/transient/publication behavior remains green.
- [ ] **T027** Run `git diff --check`.
- [ ] **T028** Perform a harmless local fake/sandbox scan proving an old historical `test/*` bridge is ignored.
- [ ] **T029** Produce a handoff with branch, exact base/head, changed files, tests, risks and rollback.

## Phase 7 — Architect review and operator activation

- [ ] **T030** Architect exact-head review before merge/activation.
- [ ] **T031** Merge only after required local tests are green; hosted CI is not an iteration mechanism.
- [ ] **T032** Operator performs one explicit installation/enable command after reviewed code is available locally.
- [ ] **T033** Run a harmless live `coord/bridge/*` pilot proving end-to-end automatic detection → Coordinator → Executor → publication with no per-package launch command.
- [ ] **T034** Only after pilot success declare persistent mode active; retain manual one-shot Coordinator as rollback path.
