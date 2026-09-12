# Handoff: Persistent Coordinator Self-Update (Specification)

Date: 2026-09-12

## Package type

**SPEC-ONLY** — no production code, installer changes, systemd units, scripts, or tests were implemented in this package. Coordinator owns commit/push/publication.

## Branch and SHAs

| Field | Value |
| --- | --- |
| Branch | `spec/002-persistent-coordinator-self-update-20260912` |
| Base SHA | `9cfa8448a9942d68ee85c8cb01d501e395c9375e` |
| Head SHA | *(Coordinator publication commit — not set by Executor)* |
| Target repo | `kkobanenko/ai-core` |
| Authoritative transition branch | `chore/coordinator-transition-v0.1-20260911` |
| Prompt | `persistent-coordinator-self-update-spec-review1-001` (Architect review fix — close self-update lock race) |

## Goal

Close the last manual-maintenance gap in the persistent Coordinator architecture: after Architect review/merge advances the reviewed transition branch on GitHub, the local Coordinator checkout and persistent `systemd --user` runner should safely advance without manual `git fetch/merge` and `systemctl restart`.

## Artifacts produced

| Path | Purpose |
| --- | --- |
| `specs/002-persistent-coordinator-self-update/spec.md` | Feature requirements, user stories, FR/SC |
| `specs/002-persistent-coordinator-self-update/research.md` | Architecture decisions |
| `specs/002-persistent-coordinator-self-update/plan.md` | Implementation plan and validation strategy |
| `specs/002-persistent-coordinator-self-update/tasks.md` | Dependency-ordered tasks for implementation package |
| `specs/002-persistent-coordinator-self-update/quickstart.md` | Operator bootstrap and normal workflow |
| `docs/handoffs/2026-09-12-persistent-coordinator-self-update-spec.md` | This handoff |

## Key design decisions (summary)

1. **Separate updater service + timer** (~60s default), not inline runner self-mutation.
2. **Single update source**: configured transition branch only; no `main`/feature refs; Architect merge is the decision boundary.
3. **Git safety**: `git fetch origin` only; clean checkout; strict `merge --ff-only`; no force/reset/clean/rebase/stash/auto-repair.
4. **Maintenance gate lock** (`coordinator-maintenance.lock`): runner holds **shared** during scan/package; updater holds **exclusive** during update window. Eliminates race between process-lock probe and `systemctl stop`.
5. **Deterministic lock ordering**: runner = maintenance(shared) → Coordinator process lock (on `run_once`); updater = updater exclusion → maintenance(exclusive) → Coordinator process lock (held through critical section).
6. **Coordinator process lock**: updater **holds** (not merely probes) during stop+merge+start; manual one-shot does not need maintenance awareness but fails safely if updater holds process lock.
7. **Post-stop failure policy**: ff failure + proven unchanged/clean → MAY restore runner once + `FAIL_CLOSED`; uncertain/changed → runner stopped + `HUMAN_REQUIRED`; never reset/clean/force or tight restart loop.
8. **Runner changes in scope**: minimal `runner.py` + `locks.py` cooperation for shared maintenance; runner is not unchanged.
9. **Installer extension**: idempotent extension of existing runner installer with `--enable-updater` bootstrap boundary.
10. **Observability**: structured status with local/remote heads, last attempt/result/reason; no secrets.
11. **Rollback**: disable updater timer/service; runner remains on last known-good checkout; manual one-shot Coordinator as emergency fallback.

## Architect review fix (this revision)

**Blocker closed**: non-blocking `coordinator.lock` probe + `systemctl stop` left a race where runner could start a new package between probe and stop.

**Resolution**: maintenance gate with shared/exclusive flock; updater acquires exclusive + holds process lock before any runner stop; runner acquires shared before each scan and skips without terminalizing candidates when updater holds exclusive.

## Required test matrix (FR-035)

1. runner holds maintenance shared → updater zero stop/merge/start
2. updater holds maintenance exclusive → runner skips scan, no terminal failures
3. updater holds process lock during stop+merge+start
4. concurrent fake harness: no deadlock
5. ff failure + proven unchanged clean → runner restored once, `FAIL_CLOSED`
6. ff failure + uncertain/changed → runner stopped, `HUMAN_REQUIRED`
7. no-op path never stops runner

## Open design risks

| Risk | Mitigation in spec/plan |
| --- | --- |
| Runner stopped but ff-only fails | Post-stop policy: recoverable only if unchanged+clean proven; else `HUMAN_REQUIRED` |
| Race: runner starts package between probe and stop | **Closed** — maintenance gate exclusive before stop |
| Concurrent updater timer invocations | Updater exclusion lock for full oneshot |
| Runner restarted under updater maintenance exclusive | Runner may start but must not process candidates until exclusive released |
| Manual one-shot during update | Updater holds process lock; document exceptional race if manual precedes acquisition |
| Config drift between runner and updater repo roots | Installer validates consistency; parser fail-closed |
| Operator dirty local changes on transition checkout | Refuse update; never auto-stash/clean |
| Network/GitHub outage | `fetch_error`; retry next cycle; no runner restart |
| Over-aggressive timer cadence | Default 60s; minimum 30s enforced in config parser |
| Bootstrap skipped | Without `--enable-updater`, no automatic advance (explicit boundary) |

## Proposed next implementation package boundaries

**In scope** (suggested branch `feat/002-persistent-coordinator-self-update-20260912`):

- `tools/dev_coordinator/updater.py`, `updater_config.py`
- `tools/dev_coordinator/locks.py` — `MaintenanceGateLock` (shared/exclusive)
- `tools/dev_coordinator/runner.py` — shared maintenance before scan (minimal)
- `ops/systemd/ai-core-dev-coordinator-updater.{service,timer}.in`
- Extension of `scripts/install_dev_coordinator_runner.py` (`--enable-updater`)
- `tests/test_dev_coordinator_updater.py`, `tests/test_dev_coordinator_updater_install.py`, runner lock cooperation tests
- `docs/coordination/PERSISTENT_RUNNER.md` self-update section
- Implementation handoff after local test gate

**Out of scope**:

- `src/ai_core/**`, providers, runtime routing, tracing, consumers
- platform-control shared contract changes (ADR required if needed)
- manual one-shot maintenance-gate awareness
- hosted CI / workflow_dispatch
- live systemd enable in automated tests
- PR creation, merge, tag, release, deploy by Executor
- `.specify/memory/constitution.md` changes

## Tests run (Executor)

| Check | Result |
| --- | --- |
| Local pytest | Not applicable — spec-only package |
| Hosted CI | Forbidden (`hosted_ci: forbidden`) |
| `git diff --check` | Coordinator must run at publication |

## Rollback

Revert spec publication commit on branch `spec/002-persistent-coordinator-self-update-20260912`. No workstation services or code behavior changes — specification artifacts only.

## Platform coordination

- Reviewed `AGENTS.md` and `/home/kok4444/projects/platform-control/coordination/current-initiative.yaml`.
- No shared contracts, ports, provider/fallback, tracing, or deployment changes.
- No `pending_decision` resolved.
- No deployment lock required (spec-only).
- ai-core write ownership: single-writer policy respected (Coordinator publication).

## Executor actions not performed (by design)

- `git commit` / `git push`
- PR creation or merge
- Hosted CI
- systemd mutation on host
- Production code implementation
