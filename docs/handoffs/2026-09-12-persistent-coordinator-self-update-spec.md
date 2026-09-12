# Handoff: Persistent Coordinator Self-Update (Specification)

Date: 2026-09-12

## Package type

**SPEC-ONLY** — no production code, installer changes, systemd units, scripts, or tests were implemented in this package. Coordinator owns commit/push/publication.

## Branch and SHAs

| Field | Value |
| --- | --- |
| Branch | `spec/002-persistent-coordinator-self-update-20260912` |
| Base SHA | `e41019b5f63589bc450eb5f29230ab7df027eabf` |
| Head SHA | *(Coordinator publication commit — not set by Executor)* |
| Target repo | `kkobanenko/ai-core` |
| Authoritative transition branch | `chore/coordinator-transition-v0.1-20260911` |

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
4. **Lock coordination**: non-blocking probe of existing `coordinator.lock`; skip/retry when package active; updater exclusion lock for concurrent timer runs.
5. **Runner lifecycle**: stop → re-verify → ff-only → restart runner exactly once only on successful head change; no restart on NOOP/failure.
6. **Installer extension**: idempotent extension of existing runner installer with `--enable-updater` bootstrap boundary.
7. **Observability**: structured status with local/remote heads, last attempt/result/reason; no secrets.
8. **Rollback**: disable updater timer/service; runner remains on last known-good checkout; manual one-shot Coordinator as emergency fallback.

## Open design risks

| Risk | Mitigation in spec/plan |
| --- | --- |
| Runner stopped but ff-only fails | Fail-closed state `ff_refused`; no auto-restart loop; operator recovery documented |
| Race: Coordinator starts between lock check and runner stop | Re-verify lock after stop before merge |
| Concurrent updater timer invocations | Updater exclusion lock for full oneshot |
| Config drift between runner and updater repo roots | Installer validates consistency; parser fail-closed |
| Operator dirty local changes on transition checkout | Refuse update; never auto-stash/clean |
| Network/GitHub outage | `fetch_error`; retry next cycle; no runner restart |
| Over-aggressive timer cadence | Default 60s; minimum 30s enforced in config parser |
| Bootstrap skipped | Without `--enable-updater`, no automatic advance (explicit boundary) |

## Proposed next implementation package boundaries

**In scope** (suggested branch `feat/002-persistent-coordinator-self-update-20260912`):

- `tools/dev_coordinator/updater.py`, `updater_config.py`
- `ops/systemd/ai-core-dev-coordinator-updater.{service,timer}.in`
- Extension of `scripts/install_dev_coordinator_runner.py` (`--enable-updater`)
- `tests/test_dev_coordinator_updater.py`, `tests/test_dev_coordinator_updater_install.py`
- `docs/coordination/PERSISTENT_RUNNER.md` self-update section
- Implementation handoff after local test gate

**Out of scope**:

- `src/ai_core/**`, providers, runtime routing, tracing, consumers
- platform-control shared contract changes (ADR required if needed)
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
