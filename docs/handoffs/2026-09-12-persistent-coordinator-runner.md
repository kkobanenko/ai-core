# Handoff: Persistent Coordinator Runner

Date: 2026-09-12

## Branch and SHAs

| Field | Value |
| --- | --- |
| Branch | `feat/001-persistent-coordinator-runner-20260912` |
| Base SHA | `f738107fd405e1fa22fa833d513752f8fa17decb` |
| Head SHA | *(Coordinator publication commit — not set by Executor)* |

## Changed files (allowed paths)

- `tools/dev_coordinator/runner_config.py` — strict JSON config parser
- `tools/dev_coordinator/managed_worktrees.py` — safe managed worktree prep
- `tools/dev_coordinator/runner.py` — poll/discover/schedule/delegate loop
- `scripts/install_dev_coordinator_runner.py` — idempotent user-systemd installer
- `ops/systemd/ai-core-dev-coordinator-runner.service.in` — unit template
- `tests/test_dev_coordinator_runner.py` — runner/config/worktree tests
- `tests/test_dev_coordinator_runner_install.py` — installer tests
- `docs/coordination/PERSISTENT_RUNNER.md` — architecture, safety, activation
- `docs/coordination/TRANSITION_PLAN.md` — S2A finished / Spec Kit-native note
- `specs/001-persistent-coordinator-runner/tasks.md` — checkbox updates
- `specs/001-persistent-coordinator-runner/quickstart.md` — aligned with implementation

## Tests run (Executor)

Shell access was unavailable in the Executor session. Coordinator must run:

| Check | Command |
| --- | --- |
| New runner tests | `PYTHONPATH=. pytest tests/test_dev_coordinator_runner.py tests/test_dev_coordinator_runner_install.py -q` |
| Existing Coordinator suite | `PYTHONPATH=. pytest tests/test_dev_coordinator.py -q` |
| Whitespace | `git diff --check` |

## Risks

- Managed worktree path scheme must match Architect-declared `target_worktree` exactly; mismatches fail closed.
- Branch checked out outside managed root blocks package until operator resolves collision.
- Runner terminal state is scheduling idempotency only; Coordinator claim remains authoritative for exactly-once execution.
- Network outages delay detection; no package state is manufactured on fetch failure.
- Service activation changes workstation behavior; operator must run installer with `--enable` explicitly after review.

## Rollback

1. `systemctl --user disable --now ai-core-dev-coordinator-runner.service` (if enabled).
2. Remove or retain `~/.config/ai-core-dev-coordinator/runner.json` and runner state as desired.
3. Revert feature branch / publication commit.
4. Manual one-shot Coordinator remains available throughout.

## Operational notes

- **Service activation NOT performed** by Executor or implementation tests.
- **Hosted CI NOT requested** (`hosted_ci: forbidden` preserved).
- **Publication commit/push** owned by Coordinator after Executor exit; Executor did not commit or push.
