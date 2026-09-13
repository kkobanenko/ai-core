# Feature Specification: Persistent Coordinator Runner

**Feature Branch**: `feat/001-persistent-coordinator-runner-20260912`

**Created**: 2026-09-12

**Status**: Ready for implementation

**Input**: User request: after saying `Твой ход`, no manual Coordinator launch should be required.

## User Scenarios & Testing

### User Story 1 - Automatic bounded execution after Architect publication (Priority: P1)

As the operator, I want a local always-on runner to notice a newly published Architect work package and start the already-tested one-shot Coordinator without me opening a terminal.

**Why this priority**: This removes the remaining manual message-bus step while preserving the existing Architect → Coordinator → Cursor separation.

**Independent Test**: Publish one valid `EXECUTOR_READY` package on a new managed bridge branch and verify that the runner creates the declared bridge/executor worktrees, invokes Coordinator once, and the target remote branch receives the verified publication commit without any manual launch command.

**Acceptance Scenarios**:

1. **Given** the runner service is active and a valid new bridge branch matching `coord/bridge/*` exists in an allowlisted repository, **When** its prompt is `EXECUTOR_READY`, **Then** the package is launched at most once and Coordinator owns validation/commit/push/remote verification.
2. **Given** a valid package has already reached a terminal runner result for the same bridge SHA, **When** the polling loop sees it again, **Then** it is not relaunched.
3. **Given** the Architect publishes a new SHA on the same managed bridge branch, **When** the runner sees it, **Then** it treats the new SHA as a new candidate while existing Coordinator exactly-once claim semantics still apply.

---

### User Story 2 - Fail closed on unsafe or unauthorized packages (Priority: P1)

As the operator, I need persistent automation to remain less powerful than the Architect and governance, so that discovery of a malformed or hostile branch cannot execute arbitrary work.

**Why this priority**: Persistent automation increases blast radius unless discovery, repository, path, branch, and prompt checks remain strict.

**Independent Test**: Present packages with a wrong branch prefix, non-allowlisted repository, target `main`, worktree outside the managed root, missing metadata, wrong base SHA, dirty worktree, unsupported hosted-CI policy, or `max_executor_runs != 1`; verify zero Executor launches.

**Acceptance Scenarios**:

1. **Given** a remote branch outside `coord/bridge/*`, **When** scanning occurs, **Then** the runner ignores it completely.
2. **Given** an `EXECUTOR_READY` prompt targeting a repository not present in runner config, **When** scanning occurs, **Then** the package is recorded as rejected and no worktree/Executor mutation occurs.
3. **Given** a package whose declared target worktree resolves outside the configured managed worktree root, **When** scanning occurs, **Then** it fails closed.
4. **Given** a target branch equal to `main` or `master`, **When** scanning occurs, **Then** it fails closed before worktree creation.

---

### User Story 3 - Survive terminal closure and ordinary workstation restarts (Priority: P2)

As the operator, I want the runner to continue without a terminal and start automatically with my user session.

**Why this priority**: The current `nohup` workflow still depends on a manual terminal command for every package.

**Independent Test**: Enable the user service, close all terminals, publish a valid package, and verify execution. Restart the service and verify already-terminal package SHAs are not duplicated.

**Acceptance Scenarios**:

1. **Given** the service is enabled, **When** the interactive terminal closes, **Then** the runner remains active.
2. **Given** the user service restarts, **When** previously terminal bridge SHAs are scanned, **Then** they remain skipped.
3. **Given** GitHub/network access is temporarily unavailable, **When** a poll fails, **Then** the service stays alive, records the error, and retries scanning later without manufacturing package state.

---

### User Story 4 - Operator-visible status and recovery evidence (Priority: P2)

As the operator, I want to know whether automation is idle, running, successful, or blocked without inspecting hidden state manually.

**Independent Test**: Run status commands after idle, success, and fail-closed cases and verify structured state plus journal/per-package logs identify bridge repo, branch, SHA, prompt ID, target repo/branch, final status, and log path.

**Acceptance Scenarios**:

1. **Given** a completed package, **When** status is queried, **Then** the latest terminal result and remote publication SHA are visible.
2. **Given** a fail-closed package, **When** status is queried, **Then** the rejection reason is visible and no automatic claim recovery is attempted.

### Edge Cases

- Old R1–R6/test bridge branches exist: they MUST NOT be scanned because they do not use the new `coord/bridge/*` namespace.
- A service dies after Coordinator claim acquisition: the runner MUST NOT auto-reclaim or rerun that prompt; existing exactly-once safety remains authoritative and the package becomes operator/Architect review material.
- A remote target branch does not exist or does not point to the declared base SHA: fail closed.
- A matching local branch/worktree already exists outside the managed root: fail closed rather than reuse an arbitrary checkout.
- A worktree exists under the managed root from a prior attempt: reuse is permitted only if repo/branch/HEAD/cleanliness exactly match the package declaration.
- Multiple ready packages exist: process serially, one Executor package at a time.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST provide a persistent local runner process supervised by `systemd --user`.
- **FR-002**: The runner MUST poll only explicitly configured local repository clones and fetch their `origin` refs without force operations.
- **FR-003**: The runner MUST discover only remote bridge branches matching the exact configured prefix `coord/bridge/*`.
- **FR-004**: The runner MUST inspect `docs/agent-bridge/next-prompt.md` from the remote bridge ref and consider only metadata state `EXECUTOR_READY` executable.
- **FR-005**: The runner MUST require `target_repo` to exist in an explicit repo→local-clone allowlist.
- **FR-006**: The runner MUST reject target branches `main` and `master` and MUST NOT create remote branches; Architect remains responsible for publishing bridge and target branches.
- **FR-007**: The runner MUST require the declared `target_worktree` to resolve beneath one configured managed-worktree root.
- **FR-008**: The runner MUST create or reuse bridge and executor worktrees only when repo, branch, HEAD/base SHA, remote ref, and clean-state checks are exact.
- **FR-009**: The runner MUST invoke the existing one-shot Coordinator instead of duplicating publication, claim, transient cleanup, safety, or Executor-launch logic.
- **FR-010**: Execution MUST remain serial: at most one active package per runner process.
- **FR-011**: The runner MUST persist per-bridge-SHA terminal state locally so repeated polls do not repeatedly invoke already-terminal packages.
- **FR-012**: A changed remote bridge SHA MAY be reconsidered, but Coordinator claim semantics MUST remain the final exactly-once authority.
- **FR-013**: The runner MUST NOT automatically reclaim claims, force-update refs, merge PRs, trigger hosted CI, tag, release, deploy, or make architectural/governance decisions.
- **FR-014**: Network/fetch errors MUST be logged and retried on later polls without changing package state to success.
- **FR-015**: The runner MUST emit structured logs and a machine-readable local state file containing package identity and terminal result.
- **FR-016**: Installation MUST be idempotent and generate/enable a `systemd --user` service using absolute paths for Python, Coordinator repo root, agent binary, config, and logs/state.
- **FR-017**: Initial configuration MUST support exactly the currently authorized bridge repositories `kkobanenko/ai-core` and `kkobanenko/platform-control`; adding other repositories is a separate explicit config/operator action.
- **FR-018**: Poll interval MUST be configurable and default to 15 seconds.
- **FR-019**: The first implementation MUST retain `docs/agent-bridge/next-prompt.md` as the execution transport, while the Spec Kit `spec.md`, `plan.md`, and `tasks.md` are the authoritative feature definition for this package.
- **FR-020**: No ai-core runtime/provider/tracing/library behavior may change as part of this feature.

### Key Entities

- **RunnerConfig**: poll interval, Coordinator repo root, managed worktree root, agent executable, allowlisted repositories and local clone paths, bridge prefix.
- **BridgeCandidate**: bridge repository, remote branch, remote SHA, prompt content, prompt ID and parsed target declaration.
- **RunnerPackageState**: identity `(bridge_repo, bridge_branch, bridge_sha)`, prompt ID, target repo/branch, lifecycle result, timestamps, Coordinator log/result reference.
- **ManagedWorktree**: a bridge or target checkout rooted strictly beneath the configured managed root.

## Success Criteria

### Measurable Outcomes

- **SC-001**: After one-time service activation, a valid newly published package starts without any operator terminal command.
- **SC-002**: Under normal network conditions, a new package is detected within 30 seconds with the default configuration.
- **SC-003**: Repeated polling of an unchanged terminal bridge SHA produces zero duplicate Executor launches.
- **SC-004**: Every tested unsafe case in User Story 2 produces zero Executor launches and a recorded fail-closed reason.
- **SC-005**: Existing Coordinator publication/claim/transient behavior remains covered by its current tests, and new runner tests cover discovery, allowlisting, worktree management, restart/idempotency, and service configuration.
- **SC-006**: Closing the terminal has no effect on the active runner; after user-session startup the enabled service returns to active state without a per-package manual command.

## Assumptions

- The workstation is on and the user session/systemd user manager is available; this feature does not execute while the machine is powered off.
- Git authentication and the Cursor `agent` binary continue to work for the user account.
- Architect continues to create remote bridge and target branches through GitHub before the runner can execute a package.
- Exceptional fail-closed/HUMAN_REQUIRED states may still require operator intervention; the goal is elimination of the normal per-package launch command, not removal of all human recovery paths.
- The existing `.specify/memory/constitution.md` is an unratified template, so `AGENTS.md`, platform-control governance, and `docs/coordination/TRANSITION_PLAN.md` provide the operative gates for this cycle.
