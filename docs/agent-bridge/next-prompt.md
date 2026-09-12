---
coord_version: 1
state: EXECUTOR_READY
prompt_id: persistent-coordinator-self-update-spec-review1-001
target_repo: kkobanenko/ai-core
target_branch: spec/002-persistent-coordinator-self-update-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/spec-002-persistent-coordinator-self-update-20260912
base_sha: 9cfa8448a9942d68ee85c8cb01d501e395c9375e
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: specs/002-persistent-coordinator-self-update/spec.md, specs/002-persistent-coordinator-self-update/plan.md, specs/002-persistent-coordinator-self-update/research.md, specs/002-persistent-coordinator-self-update/tasks.md, specs/002-persistent-coordinator-self-update/quickstart.md, docs/handoffs/2026-09-12-persistent-coordinator-self-update-spec.md
required_paths: specs/002-persistent-coordinator-self-update/spec.md, specs/002-persistent-coordinator-self-update/plan.md, specs/002-persistent-coordinator-self-update/research.md, specs/002-persistent-coordinator-self-update/tasks.md, specs/002-persistent-coordinator-self-update/quickstart.md, docs/handoffs/2026-09-12-persistent-coordinator-self-update-spec.md
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "spec(coord): close self-update lock race"
---

# Architect review fix — close self-update race

This remains SPEC-ONLY. Do not implement code.

The current spec has a correctness blocker: a non-blocking probe of the existing Coordinator process lock followed by `systemctl stop runner` leaves a race window in which the runner can begin a new package between the probe and stop. The implementation must not rely on timing to avoid interrupting a package.

Revise the spec/plan/research/tasks/quickstart/handoff so the architecture has deterministic lock ordering and no such race.

## Required locking model

Introduce a dedicated **maintenance gate lock** coordinated by both the persistent runner and updater.

Preferred model:

- Persistent runner acquires the maintenance gate in **shared** mode before each scan and holds it through candidate processing / any delegated `run_once` work for that scan. If shared acquisition is unavailable because updater holds exclusive maintenance, the runner skips that scan without recording candidates as terminal failures and retries on the normal poll cadence.
- Updater acquires an updater-instance exclusion lock first, then acquires the maintenance gate in **exclusive** mode. Exclusive acquisition must be non-blocking/fail-safe; if runner has an active scan/package, updater returns SKIPPED and retries later.
- After exclusive maintenance is held, updater acquires and HOLDS the existing Coordinator process lock for the critical update window. If that lock cannot be acquired (for example a manual one-shot Coordinator is active), updater releases maintenance and returns SKIPPED.
- Lock ordering must be explicit and consistent to avoid deadlock: runner path = maintenance(shared) → Coordinator process lock when `run_once` launches; updater path = updater exclusion → maintenance(exclusive) → Coordinator process lock.
- Once updater holds maintenance-exclusive + Coordinator process lock, no persistent-runner package can start, and an active package cannot exist. Only then may updater stop runner, perform the verified ff-only update, and start runner if appropriate.
- A newly restarted runner may start while updater still owns maintenance-exclusive, but it must not process candidates until that gate is released.
- Manual one-shot Coordinator does not need to be automatically rewritten to understand maintenance in this feature, but updater MUST hold the existing process lock so a concurrent manual launch fails safely rather than executing during mutation. Document this exceptional race behavior.

Update implementation boundaries to permit the minimal runner/lock changes needed for shared maintenance-gate cooperation (for example `tools/dev_coordinator/runner.py` plus a small lock helper/module); do not claim runner is completely unchanged.

## Post-stop failure policy

Clarify failure handling after runner stop:

- If ff-only unexpectedly fails, updater must verify whether local HEAD/worktree remained exactly at the pre-update clean state.
- If unchanged and clean can be proven, it MAY safely restore/start the previous runner once, record FAIL_CLOSED, and retry only on a later timer cycle.
- If state cannot be proven unchanged/clean, leave runner stopped and surface HUMAN_REQUIRED/fail-closed diagnostics.
- Never enter an automatic tight restart loop and never use reset/clean/force to recover.

Tests/tasks must cover both branches of this policy.

## Required test additions

The implementation test plan must explicitly cover:

1. runner holds maintenance shared during an active scan/package → updater cannot acquire exclusive and performs zero stop/merge/start;
2. updater holds maintenance exclusive → runner skips scan without terminalizing any discovered package;
3. updater holds process lock during stop+merge+start critical section;
4. lock ordering has no deadlock in fake/concurrent harness;
5. unexpected ff failure + proven unchanged clean checkout → old runner restored once, FAIL_CLOSED recorded;
6. unexpected ff failure + uncertain/changed state → runner remains stopped, HUMAN_REQUIRED/fail-closed recorded;
7. no-op path never stops runner.

Keep every previous authority/git-safety/installer/observability boundary.

Do not implement. Do not run hosted CI. Do not create PRs or merge.

Do not commit or push yourself. Coordinator owns publication.

Finish with a concise Executor summary and stop.
