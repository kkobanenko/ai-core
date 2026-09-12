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

## Decision 4 — Coordinate with existing Coordinator process lock

**Decision**: Before stopping the runner, updater performs a non-blocking check on the same `ProcessLock` file (`${state_dir}/locks/coordinator.lock`) used by `tools.dev_coordinator.cli.run_once`. If held, skip and retry next cycle.

**Why**:

- Reuses the existing deterministic shared lock rather than inventing a second execution semaphore with ambiguous precedence.
- Prevents stopping the runner while claim + executor sequence is active.

**Additional safeguard**: updater acquires its own short-lived exclusion lock (e.g. `${state_dir}/locks/coordinator-updater.lock`) so two timer-triggered updater instances cannot interleave stop/ff/restart.

## Decision 5 — Race-safe stop → ff-only → conditional restart sequence

**Decision**: Document and implement this sequence:

```text
1. Acquire updater exclusion lock (fail → SKIP concurrent_updater)
2. git fetch origin (fail → FAIL_CLOSED fetch_error, no runner touch)
3. Read remote transition SHA; if equal to local HEAD → NOOP exit
4. Non-blocking Coordinator process lock check (held → SKIP lock_held, release exclusion)
5. Verify preconditions: clean, correct branch, expected origin, canonical repo path
6. systemctl --user stop runner service
7. Re-check process lock + cleanliness + ff-only mergeability
8. git merge --ff-only origin/<branch> (fail → FAIL_CLOSED ff_refused; runner remains stopped → surface HUMAN_REQUIRED)
9. If HEAD changed: systemctl --user start runner service exactly once
10. Persist UpdaterState + structured log; release exclusion lock
```

**Why**:

- Stopping runner before merge avoids executing half-updated code during filesystem mutation.
- Re-check after stop closes the race where Coordinator started between steps 4 and 6.
- Restart only on verified head change prevents restart loops on no-op/failure.

**Fail-safe for step 8 failure**: runner stays stopped; status reason `ff_refused` / `precondition_failed`; operator may manually restart runner on old HEAD or fix git state. Updater must not auto-restart in a tight loop.

## Decision 6 — Extend existing installer; preserve runner compatibility

**Decision**: Extend `scripts/install_dev_coordinator_runner.py` (or companion module) to optionally install:

- `ai-core-dev-coordinator-updater.service` (Type=oneshot)
- `ai-core-dev-coordinator-updater.timer` (OnUnitActiveSec=~60s, configurable)

Shared config file may gain an `updater` section or a sibling JSON under the same `ai-core-dev-coordinator` config directory. Runner `runner.json` fields remain unchanged.

**Why**:

- Operator already has a one-time activation ritual for the runner; updater activation should be the same command with an additional flag or subcommand.
- Avoids ad-hoc shell instructions that drift from implementation.

## Decision 7 — Bootstrap boundary

**Decision**: Implementation review merge delivers code + units, but automatic self-update begins only after operator runs the documented one-time `--enable-updater` (or equivalent) activation. That activation is the last required terminal command for routine transition maintenance.

**Why**:

- Enabling timer-driven git mutation is a workstation policy change deserving explicit consent.
- Matches runner package precedent (`--enable` without implicit test activation).

## Decision 8 — Observability without secrets

**Decision**: Store updater state at `${XDG_STATE_HOME}/ai-core-dev-coordinator/updater-state.json` with fields: `local_head`, `remote_head`, `last_attempt_at`, `last_result`, `reason`, `last_success_head`, `last_runner_restart_at`. Logs go to user journal for the updater service.

**Why**:

- Parallel to runner state design; supports `--status` style CLI for operators.
- No tokens, credentials, or prompt contents in updater state.

## Decision 9 — Testing with fakes only

**Decision**: pytest harnesses inject fake git, fake systemctl, and fake lock behavior; no live `systemctl enable` in tests.

**Why**:

- Consistent with runner installer tests and `hosted_ci: forbidden`.
- Allows exhaustive negative-path coverage without mutating developer workstations.

## Decision 10 — Rollback is disable updater, not uninstall runner

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
| ff-only verification | merge --ff-only + rev-parse equality | tests |
