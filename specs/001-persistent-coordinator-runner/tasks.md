# Tasks: Persistent Coordinator Runner

**Feature**: `001-persistent-coordinator-runner`

**Authority**: `spec.md` + `plan.md`; bridge prompt is execution transport only.

## Phase 1 — Config and safety foundation

- [x] **T001** Add `tools/dev_coordinator/runner_config.py` with strict stdlib JSON parsing for poll interval, Coordinator root, managed worktree root, agent path, bridge prefix and repository allowlist.
- [x] **T002** Reject unknown config keys, relative paths, duplicate repository paths, missing configured clones, unsupported bridge prefix, invalid poll intervals and empty allowlist.
- [x] **T003** Add tests for valid config and every fail-closed config case.

## Phase 2 — Managed worktree preparation

- [x] **T004** Add `tools/dev_coordinator/managed_worktrees.py` with canonical containment checks under one managed root.
- [x] **T005** Implement bridge-worktree prepare/reuse with exact repo/branch/SHA/clean checks, ff-only advance on changed SHA, and no force.
- [x] **T006** Implement executor-worktree prepare/reuse with exact target repo/branch/base SHA/clean checks.
- [x] **T007** Fail closed if a required branch is checked out outside the managed root, if a path is inconsistent, or target is `main`/`master`.
- [x] **T008** Add tests for create, safe reuse, stale/mismatched worktree, outside-root path, branch collision and missing remote ref.

## Phase 3 — Remote discovery and persistent scheduling

- [x] **T009** Add `tools/dev_coordinator/runner.py` with `--once`, persistent-loop and `--status` modes.
- [x] **T010** Fetch only configured repositories and enumerate only `refs/remotes/origin/coord/bridge/*`.
- [x] **T011** Read prompt content from the exact remote bridge ref and parse with existing `parse_next_prompt` before worktree creation.
- [x] **T012** Ignore non-ready states; fail closed on malformed ready candidates; require target repo allowlist and managed target-worktree path.
- [x] **T013** Process candidates serially and delegate execution to existing one-shot Coordinator path instead of reimplementing claim/publication logic.
- [x] **T014** Persist terminal `(bridge repo, branch, SHA)` results atomically in runner state and skip unchanged terminal candidates after restart.
- [x] **T015** Preserve Coordinator exactly-once claims; do not implement automatic claim reclaim.
- [x] **T016** Keep service alive across fetch/network errors and record structured diagnostics for later polling.
- [x] **T017** Add tests proving no discovery outside `coord/bridge/*`, serial execution, restart idempotency, changed-SHA reconsideration, network error recovery and zero duplicate launches.

## Phase 4 — Installation and service lifecycle

- [x] **T018** Add `ops/systemd/ai-core-dev-coordinator-runner.service.in` with user-service restart behavior and no privileged execution.
- [x] **T019** Add `scripts/install_dev_coordinator_runner.py` that resolves/writes absolute paths, writes config/unit idempotently and supports explicit `--enable`.
- [x] **T020** Ensure tests can inject/fake systemctl; implementation tests MUST NOT enable the real workstation service.
- [x] **T021** Add installer tests for first install, idempotent reinstall, invalid agent/Python/repo paths and generated unit contents.

## Phase 5 — Documentation and compatibility

- [x] **T022** Add `docs/coordination/PERSISTENT_RUNNER.md` describing architecture, safety boundaries, `coord/bridge/*` convention, status/logging, activation and rollback.
- [x] **T023** Update `docs/coordination/TRANSITION_PLAN.md` to record that the first Spec Kit-native package is this runner feature and that old bridge is now transport rather than specification authority for new packages.
- [x] **T024** Do not change `src/ai_core/**`, provider/runtime/tracing APIs, dependency set, old PR #3/#4/#5, or consumer repositories.

## Phase 6 — Verification

- [ ] **T025** Run focused new runner/installer tests. *(review-fix2: repaired at `4ebe7d92`; Coordinator must run pytest gate)*
- [ ] **T026** Run the complete existing Coordinator test suite to prove claim/safety/transient/publication behavior remains green. *(review-fix2: Coordinator must run full gate)*
- [ ] **T027** Run `git diff --check` against `8430a887ae063fbc1cf29a3fcf902083355c1a36..HEAD`. *(Coordinator must run)*
- [x] **T028** Perform a harmless local fake/sandbox scan proving an old historical `test/*` bridge is ignored. *(covered by `test_discover_only_coord_bridge_refs` / `test_ignore_test_prefix_branches_in_scan`)*
- [x] **T029** Produce a handoff with branch, exact base/head, changed files, tests, risks and rollback.

## Phase 7 — Architect review and operator activation

- [ ] **T030** Architect exact-head review before merge/activation.
- [ ] **T031** Merge only after required local tests are green; hosted CI is not an iteration mechanism.
- [ ] **T032** Operator performs one explicit installation/enable command after reviewed code is available locally.
- [ ] **T033** Run a harmless live `coord/bridge/*` pilot proving end-to-end automatic detection → Coordinator → Executor → publication with no per-package launch command.
- [ ] **T034** Only after pilot success declare persistent mode active; retain manual one-shot Coordinator as rollback path.
