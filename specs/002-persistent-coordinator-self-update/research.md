# Research: Persistent Coordinator Self-Update

## Decision 1 — Separate updater timer/service vs inline runner self-mutation

**Decision**: Implement self-update as a separate `systemd --user` oneshot service triggered by a conservative timer (default ~60s), not as logic inside the persistent runner loop.

**Why**:

- The runner must not mutate the checkout from which its own Python code is executing; that creates undefined behavior during import/restart and complicates crash recovery.
- A separate supervised unit matches the existing runner installation model, keeps responsibilities isolated, and allows disabling self-update without disabling package execution.
- Timer cadence can be slower than runner polling (15s) because transition-branch updates are infrequent compared with bridge discovery.

**Alternatives considered**:

- Inline self-update in `runner.py`: rejected due to self-modification hazard and coupling execution scheduling with deployment.
- Manual operator `git pull` forever: rejected; this is the remaining maintenance gap.
- `systemd` path units watching `.git/HEAD`: rejected as fragile, non-portable, and hard to fail-closed.

## Decision 2 — Only the reviewed transition branch is authoritative

**Decision**: Updater config pins exactly one branch: `chore/coordinator-transition-v0.1-20260911` (overridable only via explicit installer/config change, never via remote prompt).

**Why**:

- Coordinator tooling is released through Architect-reviewed merges on the transition branch, not through `main` or arbitrary feature branches.
- Fail-closed single-source semantics prevent a compromised prompt or misconfiguration from tracking the wrong ref.

**Rejected**:

- Tracking `main`/`master`: forbidden by governance for this tooling plane.
- Auto-merging feature branches or open PRs: would bypass Architect decision boundary.

## Decision 3 — Strict fast-forward only; never auto-repair git state

**Decision**: After `git fetch origin`, advance only if `git merge --ff-only origin/<transition-branch>` (or equivalent verified ff-only) succeeds on a clean checkout that already matches branch/origin/canonical-repo preconditions.

**Why**:

- Mirrors the proven ff-only bridge worktree advance pattern from `001-persistent-coordinator-runner`.
- Preserves local evidence when state is unsafe; operator recovery stays explicit.

**Rejected**:

- `git reset --hard`, `git pull`, `git rebase`, `git stash`, checkout switching, or auto conflict resolution: all forbidden.

## Decision 4 — Maintenance gate lock (shared runner / exclusive updater)

**Decision**: Introduce a dedicated maintenance gate lock at `${state_dir}/locks/coordinator-maintenance.lock` with `fcntl.flock` shared/exclusive modes, coordinated by both persistent runner and updater.

- **Runner**: acquire maintenance **shared** (non-blocking) before each scan; hold through candidate processing and delegated `run_once` for that scan. If exclusive held by updater, skip scan without terminalizing candidates; retry on normal poll cadence.
- **Updater**: after updater exclusion lock, acquire maintenance **exclusive** (non-blocking). If runner has active scan/package, return `SKIPPED` with zero stop/merge/start.

**Why**:

- A non-blocking probe of `coordinator.lock` followed by `systemctl stop` leaves a race window: runner can begin a new package between probe and stop. Maintenance gate closes this deterministically.
- Shared/exclusive on one file is a standard flock pattern; runner and updater paths have explicit, deadlock-free ordering.

**Rejected**:

- Process-lock probe alone before runner stop: race window remains.
- Stopping runner first then checking lock: can interrupt in-flight work.

**Implementation boundary**: extend `tools/dev_coordinator/locks.py` with `MaintenanceGateLock`; minimal changes to `tools/dev_coordinator/runner.py` to acquire/release shared maintenance around scan cycles. Runner is **not** unchanged.

## Decision 5 — Deterministic lock ordering and critical section

**Decision**: Document and implement explicit lock ordering:

**Runner path**: maintenance(shared) → Coordinator process lock (only when launching `run_once`)

**Updater path**: updater exclusion → maintenance(exclusive) → Coordinator process lock

After updater holds maintenance-exclusive + Coordinator process lock, no persistent-runner package can start. Only then: stop runner → ff-only merge → conditional restart. Release locks in reverse order.

**Coordinator process lock role**: updater **holds** (not merely probes) `coordinator.lock` for the entire stop+merge+start critical section. If acquisition fails (e.g. manual one-shot active), release maintenance exclusive and `SKIPPED`. Manual one-shot Coordinator does not need maintenance-gate awareness; holding process lock prevents concurrent manual execution during mutation (document exceptional race if manual launch precedes updater acquisition).

**Newly restarted runner**: may start while updater still owns maintenance exclusive, but must not process candidates until exclusive is released.

## Decision 5a — Race-safe updater sequence

**Decision**: Document and implement this sequence:

```text
1. Acquire updater exclusion lock (fail → SKIP concurrent_updater)
2. git fetch origin (fail → FAIL_CLOSED fetch_error, no runner touch)
3. Read remote transition SHA; if equal to local HEAD → NOOP exit (no runner stop)
4. Acquire maintenance gate EXCLUSIVE non-blocking (fail → SKIP maintenance_held)
5. Acquire Coordinator process lock non-blocking (fail → release maintenance, SKIP process_lock_held)
6. Verify preconditions: clean, correct branch, expected origin, canonical repo path, ff-only mergeability
7. systemctl --user stop runner service
8. git merge --ff-only origin/<branch>
9. On ff failure: verify HEAD/worktree unchanged+clean → MAY start runner once + FAIL_CLOSED; else HUMAN_REQUIRED, runner stopped
10. On success + HEAD changed: systemctl --user start runner exactly once
11. Release Coordinator process lock → maintenance exclusive → exclusion lock
12. Persist UpdaterState + structured log
```

**Why**:

- Steps 4–5 prove no active scan/package before stop; no timing dependence.
- Holding process lock through step 10 prevents manual one-shot interference during mutation.
- NOOP at step 3 never stops runner.

**Fail-safe for step 8–9**: never reset/clean/force; never tight restart loop. Recoverable only when pre-update state provably unchanged and clean.

## Decision 6 — Post-stop ff failure policy

**Decision**: After runner stop, if ff-only unexpectedly fails:

1. Verify local HEAD and worktree match pre-update clean snapshot.
2. **Proven unchanged/clean**: MAY restore/start runner once, record `FAIL_CLOSED` / `ff_refused_recoverable`, retry on later timer only.
3. **Uncertain or changed**: leave runner stopped, `HUMAN_REQUIRED` / `ff_refused`; no automatic recovery via reset/clean/force.

**Why**: Operator needs safe automatic recovery when mutation did not occur, but must not mask partial/corrupt state.

## Decision 7 — Extend existing installer; preserve runner compatibility

**Decision**: Extend `scripts/install_dev_coordinator_runner.py` (or companion module) to optionally install:

- `ai-core-dev-coordinator-updater.service` (Type=oneshot)
- `ai-core-dev-coordinator-updater.timer` (OnUnitActiveSec=~60s, configurable)

Shared config file may gain an `updater` section or a sibling JSON under the same `ai-core-dev-coordinator` config directory. Runner `runner.json` fields remain unchanged.

**Why**:

- Operator already has a one-time activation ritual for the runner; updater activation should be the same command with an additional flag or subcommand.
- Avoids ad-hoc shell instructions that drift from implementation.

## Decision 8 — Bootstrap boundary

**Decision**: Implementation review merge delivers code + units, but automatic self-update begins only after operator runs the documented one-time `--enable-updater` (or equivalent) activation. That activation is the last required terminal command for routine transition maintenance.

**Why**:

- Enabling timer-driven git mutation is a workstation policy change deserving explicit consent.
- Matches runner package precedent (`--enable` without implicit test activation).

## Decision 9 — Observability without secrets

**Decision**: Store updater state at `${XDG_STATE_HOME}/ai-core-dev-coordinator/updater-state.json` with fields: `local_head`, `remote_head`, `last_attempt_at`, `last_result`, `reason`, `last_success_head`, `last_runner_restart_at`. Logs go to user journal for the updater service.

**Why**:

- Parallel to runner state design; supports `--status` style CLI for operators.
- No tokens, credentials, or prompt contents in updater state.

## Decision 10 — Testing with fakes only

**Decision**: pytest harnesses inject fake git, fake systemctl, and fake lock behavior; no live `systemctl enable` in tests.

**Why**:

- Consistent with runner installer tests and `hosted_ci: forbidden`.
- Allows exhaustive negative-path coverage without mutating developer workstations.

## Decision 11 — Rollback is disable updater, not uninstall runner

**Decision**: Rollback path is `systemctl --user disable --now ai-core-dev-coordinator-updater.timer` (and service if needed). Runner remains on last successful local checkout. Manual one-shot Coordinator remains emergency fallback.

**Why**:

- Minimizes blast radius; operator can freeze tooling version without losing automation entirely.

## Open design notes (for implementation package)

| Topic | Proposed default | Change requires |
| --- | --- | --- |
| Timer interval | 60s | explicit config key + docs |
| Expected origin URL | `https://github.com/kkobanenko/ai-core.git` (canonical) | installer flag |
| Runner service name | `ai-core-dev-coordinator-runner.service` | config |
| Updater CLI module | `tools.dev_coordinator.updater` | plan/tasks |
| Maintenance gate lock | `coordinator-maintenance.lock` shared/exclusive | locks.py + runner.py |
| ff-only verification | merge --ff-only + rev-parse equality | tests |
| Post-stop recovery | restore runner once only if unchanged+clean proven | tests |
