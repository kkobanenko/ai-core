# Feature Specification: Persistent Coordinator Self-Update

**Feature Branch**: `spec/002-persistent-coordinator-self-update-20260912`

**Created**: 2026-09-12

**Status**: Ready for implementation planning

**Input**: Close the last manual-maintenance gap in the persistent Coordinator architecture: after Architect review/merge advances the authoritative Coordinator transition branch on GitHub, the local Coordinator checkout and persistent `systemd --user` runner should safely advance to that reviewed transition head without requiring the user to run `git fetch/merge` and `systemctl restart` manually.

## Scope and boundaries

This capability is **tooling-plane only**. It MUST NOT authorize or alter:

- `src/ai_core/**`, providers, runtime routing, or consumers
- platform-control governance, shared contracts, ports, or tracing
- product releases, deployments, or hosted CI as an iteration mechanism

The authoritative reviewed transition branch at specification time is:

`chore/coordinator-transition-v0.1-20260911`

Only that configured branch is eligible as an update source. No `main`/`master`, no feature branches, no arbitrary ref input, and no automatic merge of PRs or feature branches. Architect/GitHub merge remains the decision boundary.

## User Scenarios & Testing

### User Story 1 - Automatic advance after reviewed transition merge (Priority: P1)

As the operator, after Architect review merges new Coordinator tooling into the reviewed transition branch, I want my local Coordinator checkout and persistent runner to advance to that head automatically without manual `git fetch`, `git merge`, or `systemctl restart`.

**Why this priority**: This removes the remaining per-update maintenance step while preserving reviewed-change authority on GitHub.

**Independent Test**: Advance the remote transition branch by one fast-forward commit on a test clone; with updater enabled and runner idle, verify local HEAD matches remote within one update cycle and the runner service restarts exactly once.

**Acceptance Scenarios**:

1. **Given** updater is enabled, local checkout is clean on the configured transition branch, remote has exactly one new fast-forward commit, and maintenance gate + Coordinator process lock can be acquired (no active scan/package or manual one-shot), **When** the updater timer fires, **Then** local HEAD advances by strict fast-forward only and the persistent runner is restarted exactly once.
2. **Given** local HEAD already equals the remote reviewed transition head, **When** the updater runs, **Then** no git mutation occurs and the runner is not restarted.
3. **Given** Architect has not merged any new transition commit, **When** the updater runs repeatedly, **Then** behavior remains a no-op with diagnosable status.

---

### User Story 2 - Fail closed on unsafe git state (Priority: P1)

As the operator, I need self-update to refuse any state it cannot verify safely, rather than attempting repair.

**Why this priority**: Automatic git mutation on a dirty, diverged, or misconfigured checkout could destroy local evidence or run the wrong Coordinator code.

**Independent Test**: Present dirty, diverged, wrong-branch, wrong-origin, and non-canonical-repository cases; verify zero fast-forward attempts and zero runner restarts.

**Acceptance Scenarios**:

1. **Given** the local checkout has uncommitted or unstaged changes, **When** the updater runs, **Then** update is refused with a recorded reason and the runner is not restarted.
2. **Given** local and remote transition heads have diverged, **When** the updater runs, **Then** fast-forward is impossible, update is refused, and no force/reset/clean/checkout-switch/rebase/stash is attempted.
3. **Given** the checkout is not on the configured transition branch or `origin` does not match the expected canonical remote, **When** the updater runs, **Then** update is refused fail-closed.
4. **Given** `git fetch origin` fails, **When** the updater runs, **Then** the failure is logged, no local mutation occurs, and a later timer attempt may retry.

---

### User Story 3 - Do not interrupt an active work package (Priority: P1)

As the operator, I need self-update to defer while Coordinator is executing or publishing a package, using deterministic lock ordering rather than timing-dependent probes.

**Why this priority**: Stopping or restarting the runner mid-package could duplicate execution, corrupt publication, or violate exactly-once claim semantics. A non-blocking probe of the Coordinator process lock followed by `systemctl stop` leaves a race window in which the runner can begin a new package between probe and stop.

**Independent Test**: With runner holding maintenance gate shared during an active scan/package, verify updater cannot acquire exclusive maintenance, performs zero stop/merge/start, and retries later. With updater holding maintenance exclusive, verify runner skips scan without terminalizing discovered packages.

**Acceptance Scenarios**:

1. **Given** the persistent runner holds the maintenance gate in **shared** mode during an active scan or delegated `run_once` work, **When** the updater timer fires, **Then** exclusive maintenance acquisition fails non-blocking, update is `SKIPPED`, no runner stop occurs, and a later attempt retries.
2. **Given** the updater holds maintenance gate **exclusive** and Coordinator process lock, **When** the runner poll fires, **Then** shared maintenance acquisition fails, the runner skips that scan without recording candidates as terminal failures, and retries on the normal poll cadence.
3. **Given** preconditions pass and no active scan/package holds shared maintenance, **When** a new remote head exists, **Then** updater follows the deterministic sequence: updater exclusion → maintenance(exclusive) → Coordinator process lock → stop runner → fast-forward → conditional restart → release locks in reverse order.
4. **Given** runner stop succeeds but fast-forward unexpectedly fails, **When** local HEAD/worktree can be proven exactly unchanged and clean at the pre-update state, **Then** updater MAY restore/start the previous runner once, record `FAIL_CLOSED`, and retry only on a later timer cycle.
5. **Given** runner stop succeeds but fast-forward fails and checkout state cannot be proven unchanged/clean, **When** the sequence completes, **Then** runner remains stopped, `HUMAN_REQUIRED`/`FAIL_CLOSED` diagnostics are surfaced, and no automatic tight restart loop or reset/clean/force recovery is attempted.

---

### User Story 4 - One-time bootstrap, then hands-off operation (Priority: P2)

As the operator, I want a single deliberate activation after implementation review; afterward, reviewed transition updates should not require per-update terminal commands.

**Why this priority**: Enabling always-on self-update is an operational change; the bootstrap boundary must be explicit.

**Independent Test**: Run installer once with updater enable flag; verify timer/service units exist. Simulate a later reviewed transition advance without rerunning installer; verify automatic update still works.

**Acceptance Scenarios**:

1. **Given** implementation is reviewed but updater has not been activated, **When** remote transition advances, **Then** no automatic local advance occurs until operator runs the documented one-time activation.
2. **Given** updater was activated once, **When** future reviewed transition commits land on GitHub, **Then** local advance and runner restart happen without additional operator commands.
3. **Given** installer is rerun idempotently, **When** config paths and units already exist, **Then** installation remains compatible with existing runner config and does not duplicate conflicting services.

---

### User Story 5 - Operator-visible update status and safe rollback (Priority: P2)

As the operator, I want to see whether self-update is current, skipped, or blocked, and I want to disable self-update without losing the persistent runner on its last known-good checkout.

**Independent Test**: Query status after no-op, success, skip-due-to-lock, and fail-closed cases; disable updater timer/service and verify runner remains usable; manual one-shot Coordinator remains available.

**Acceptance Scenarios**:

1. **Given** any updater attempt, **When** status is queried, **Then** structured output shows local head, remote reviewed head when known, last attempt time/result, and skip/fail reason.
2. **Given** updater timer/service is disabled, **When** remote transition advances, **Then** local checkout is unchanged by automation and the persistent runner continues on last known-good code until manual intervention.
3. **Given** self-update is disabled or failing, **When** the operator needs emergency execution, **Then** manual one-shot Coordinator remains available.

### Edge Cases

- Remote transition branch temporarily unavailable: fail closed, retry later; no runner restart.
- Local checkout path differs from configured canonical Coordinator repo root: fail closed.
- Runner service already stopped before update attempt: fast-forward may still proceed; restart only if head actually changed.
- Updater crashes after runner stop but before restart: next cycle must detect stopped runner and either complete restart (only when state is provably unchanged/clean) or surface `HUMAN_REQUIRED` without a tight restart loop.
- Two updater instances must not run concurrently; updater uses its own exclusion lock separate from but coordinated with the maintenance gate and Coordinator process lock.
- A newly restarted runner may start while updater still owns maintenance exclusive, but it MUST NOT process candidates until maintenance exclusive is released.
- Manual one-shot Coordinator does not need to understand maintenance gate in this feature, but updater MUST hold the existing Coordinator process lock during the critical update window so a concurrent manual launch fails safely rather than executing during mutation; document this exceptional race behavior.
- `git fetch origin` is allowed; no other remotes, no `git pull` with merge/rebase semantics, no worktree mutation outside the configured Coordinator checkout.
- Secrets MUST NOT be written to updater state or logs.

## Requirements

### Functional Requirements

#### Authority and update source

- **FR-001**: The system MUST update only from a single configured reviewed transition branch (default `chore/coordinator-transition-v0.1-20260911`).
- **FR-002**: The system MUST NOT accept arbitrary ref input, `main`/`master`, or feature-branch names as update sources.
- **FR-003**: The system MUST NOT merge PRs, create branches, or advance local state based on unreviewed remote refs.

#### Git safety

- **FR-004**: The system MAY run `git fetch origin` against the configured Coordinator checkout only.
- **FR-005**: The system MUST verify the checkout is the expected canonical Coordinator repository, on the configured transition branch, with a clean worktree, and with the expected `origin` remote before mutating local refs.
- **FR-006**: Local advance MUST use strict fast-forward semantics only (`git merge --ff-only` or equivalent verified fast-forward).
- **FR-007**: The system MUST NOT use force, reset, clean, checkout branch switching, stash, rebase, branch deletion, or automatic conflict resolution.
- **FR-008**: Diverged, dirty, wrong-origin, wrong-branch, or non-canonical checkout states MUST fail closed and be reported; they MUST NOT be repaired automatically.

#### Active work protection (maintenance gate + lock ordering)

- **FR-009**: The system MUST introduce a dedicated **maintenance gate lock** at `${state_dir}/locks/coordinator-maintenance.lock`, coordinated by both the persistent runner and updater, supporting shared (runner) and exclusive (updater) acquisition modes via `fcntl.flock`.
- **FR-010**: The persistent runner MUST acquire maintenance gate **shared** before each scan and hold it through candidate processing and any delegated `run_once` work for that scan. If shared acquisition fails because updater holds exclusive maintenance, the runner MUST skip that scan without recording candidates as terminal failures and retry on the normal poll cadence.
- **FR-011**: The updater MUST acquire updater-instance exclusion lock first, then acquire maintenance gate **exclusive** non-blocking/fail-safe. If exclusive acquisition fails (runner has active scan/package), updater MUST return `SKIPPED` with zero stop/merge/start and retry later.
- **FR-012**: After exclusive maintenance is held, updater MUST acquire and **hold** the existing Coordinator process lock (`${state_dir}/locks/coordinator.lock`) for the critical update window. If process lock cannot be acquired (e.g. manual one-shot Coordinator active), updater MUST release maintenance exclusive and return `SKIPPED`.
- **FR-013**: Lock ordering MUST be explicit and deadlock-free: runner path = maintenance(shared) → Coordinator process lock when `run_once` launches; updater path = updater exclusion → maintenance(exclusive) → Coordinator process lock. Locks MUST be released in reverse acquisition order.
- **FR-014**: Once updater holds maintenance-exclusive + Coordinator process lock, no persistent-runner package can start and an active package cannot exist. Only then MAY updater stop runner, perform verified ff-only update, and start runner if appropriate.
- **FR-015**: A newly restarted runner MAY start while updater still owns maintenance-exclusive, but MUST NOT process candidates until maintenance exclusive is released.
- **FR-016**: Manual one-shot Coordinator does not need maintenance-gate awareness in this feature, but updater MUST hold Coordinator process lock so concurrent manual launch fails safely; document exceptional manual-launch race behavior.
- **FR-017**: The implementation MUST NOT rely on timing or non-blocking process-lock probe alone to avoid interrupting a package; maintenance gate cooperation in the runner is required (minimal changes to `tools/dev_coordinator/runner.py` plus a small lock helper/module).

#### Post-stop failure policy

- **FR-018**: If ff-only unexpectedly fails after runner stop, updater MUST verify whether local HEAD/worktree remained exactly at the pre-update clean state.
- **FR-019**: If unchanged and clean can be proven, updater MAY safely restore/start the previous runner once, record `FAIL_CLOSED`, and retry only on a later timer cycle.
- **FR-020**: If state cannot be proven unchanged/clean, updater MUST leave runner stopped and surface `HUMAN_REQUIRED`/`FAIL_CLOSED` diagnostics.
- **FR-021**: Updater MUST NEVER enter an automatic tight restart loop and MUST NEVER use reset/clean/force to recover.

#### Service supervision

- **FR-022**: The persistent runner MUST remain supervised by `systemd --user` as today.
- **FR-023**: Self-update MUST be implemented as a separately supervised scheduled service (timer + oneshot service), not by having the runner mutate its own checkout inline.
- **FR-024**: Default update cadence MUST be conservative (approximately 60 seconds), documented, configurable if justified, and MUST NOT be faster than operationally necessary.
- **FR-025**: The runner MUST be restarted only after a successful local head change.
- **FR-026**: When already at remote head, the updater MUST NOT restart the runner (no-op path never stops runner).
- **FR-027**: A failed or skipped update MUST leave a diagnosable state and MUST NOT cause a restart loop.

#### Installer and activation

- **FR-028**: The existing idempotent installer design MUST be extended rather than requiring ad-hoc shell setup.
- **FR-029**: Existing runner config paths and runner installation MUST remain compatible.
- **FR-030**: One final operator activation/update after implementation review is required; after that, reviewed transition updates MUST NOT require per-update terminal commands.
- **FR-031**: The bootstrap boundary MUST be documented explicitly in quickstart and handoff material.

#### Observability and state

- **FR-032**: Structured logs and a machine-readable status surface MUST expose: current local Coordinator head, remote reviewed head when known, last update attempt timestamp, last result, and reason for skip/fail-closed.
- **FR-033**: Updater state MUST NOT store secrets.

#### Testing and governance

- **FR-034**: Automated tests MUST cover: already-current no-op (no runner stop); clean fast-forward; dirty refusal; diverged refusal; wrong branch/origin refusal; successful update triggers exactly one runner restart; failed/no-op update triggers no restart; installer idempotence.
- **FR-035**: Automated tests MUST explicitly cover maintenance-gate and post-stop failure scenarios:
  1. runner holds maintenance shared during active scan/package → updater cannot acquire exclusive and performs zero stop/merge/start;
  2. updater holds maintenance exclusive → runner skips scan without terminalizing any discovered package;
  3. updater holds Coordinator process lock during stop+merge+start critical section;
  4. lock ordering has no deadlock in fake/concurrent harness;
  5. unexpected ff failure + proven unchanged clean checkout → old runner restored once, `FAIL_CLOSED` recorded;
  6. unexpected ff failure + uncertain/changed state → runner remains stopped, `HUMAN_REQUIRED`/`FAIL_CLOSED` recorded;
  7. no-op path never stops runner.
- **FR-036**: Tests MUST use fake git/systemctl/lock behavior; live systemd mutation on the host is forbidden in tests.
- **FR-037**: Hosted CI remains forbidden for this package unless separately authorized.
- **FR-038**: No `src/ai_core/**`, provider/runtime/tracing, consumer repository, platform-control contract, or deployment behavior may change as part of this feature. Minimal runner/lock changes for maintenance-gate cooperation are in scope.

### Key Entities

- **UpdaterConfig**: coordinator repo root, expected origin URL, transition branch name, poll/timer interval, runner service name, state/log locations.
- **UpdaterState**: local head, remote head (last known), last attempt time, last result (`NOOP`, `SUCCESS`, `SKIPPED`, `FAIL_CLOSED`), reason code, previous head on last success.
- **UpdateAttempt**: one timer-triggered evaluation with precondition checks, optional runner stop, optional fast-forward, optional runner restart, and terminal classification.
- **MaintenanceGateLock**: shared/exclusive flock at `${state_dir}/locks/coordinator-maintenance.lock`; runner holds shared during scan/package; updater holds exclusive during update window.
- **CoordinatorProcessLock**: existing exclusive lock at `${state_dir}/locks/coordinator.lock`; held by one-shot Coordinator and by updater during critical stop+merge+start window.
- **UpdaterExclusionLock**: separate short-lived lock at `${state_dir}/locks/coordinator-updater.lock` preventing concurrent updater runs.

## Success Criteria

### Measurable Outcomes

- **SC-001**: After one-time updater activation, a newly merged reviewed transition commit is reflected locally without any manual `git fetch/merge` or `systemctl restart` command.
- **SC-002**: Under normal network conditions and idle runner, a single new fast-forward transition commit is applied within two updater cycles at default cadence.
- **SC-003**: Every tested unsafe git case produces zero local mutation and zero runner restart.
- **SC-004**: When maintenance shared or Coordinator process lock blocks update, updater produces zero runner stop/restart events and retries successfully after gate release.
- **SC-004a**: When updater holds maintenance exclusive, runner produces zero terminal candidate failures for skipped scans and resumes normal processing after gate release.
- **SC-005**: A successful head change produces exactly one runner restart; no-op and failed attempts produce zero runner restarts.
- **SC-006**: Disabling updater timer/service leaves the persistent runner usable on its last known-good checkout; manual one-shot Coordinator remains available.
- **SC-007**: Existing runner and Coordinator safety tests remain green; new updater tests cover FR-034 and FR-035 scenarios with fakes only.

## Assumptions

- The workstation is on and the user systemd session is available; self-update does not run while the machine is powered off.
- Git authentication to GitHub continues to work for the operator account.
- Architect continues to land Coordinator tooling changes only via reviewed merge into the configured transition branch.
- The persistent runner package (`001-persistent-coordinator-runner`) is implemented and activatable; self-update builds on that foundation.
- The existing Coordinator process lock at `${state_dir}/locks/coordinator.lock` remains the authoritative in-flight execution guard for one-shot Coordinator; maintenance gate adds deterministic runner/updater coordination on top.
- Shared/exclusive flock semantics on a single lock file require a small lock helper (e.g. extending `tools/dev_coordinator/locks.py`); runner acquires shared maintenance before each scan cycle.
- `.specify/memory/constitution.md` is unratified; operative governance is `AGENTS.md`, platform-control, and `docs/coordination/TRANSITION_PLAN.md`.
- Exceptional fail-closed states may still require operator intervention; the goal is elimination of routine per-update maintenance, not removal of all human recovery paths.
