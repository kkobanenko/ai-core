---
coord_version: 1
state: EXECUTOR_READY
prompt_id: persistent-coordinator-runner-impl-001
target_repo: kkobanenko/ai-core
target_branch: feat/001-persistent-coordinator-runner-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/feat-001-persistent-coordinator-runner-20260912
base_sha: f738107fd405e1fa22fa833d513752f8fa17decb
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: tools/dev_coordinator/runner.py, tools/dev_coordinator/runner_config.py, tools/dev_coordinator/managed_worktrees.py, scripts/install_dev_coordinator_runner.py, ops/systemd/ai-core-dev-coordinator-runner.service.in, tests/test_dev_coordinator_runner.py, tests/test_dev_coordinator_runner_install.py, docs/coordination/PERSISTENT_RUNNER.md, docs/coordination/TRANSITION_PLAN.md, specs/001-persistent-coordinator-runner/tasks.md, specs/001-persistent-coordinator-runner/quickstart.md, docs/handoffs/2026-09-12-persistent-coordinator-runner.md
required_paths: tools/dev_coordinator/runner.py, tools/dev_coordinator/runner_config.py, tools/dev_coordinator/managed_worktrees.py, scripts/install_dev_coordinator_runner.py, ops/systemd/ai-core-dev-coordinator-runner.service.in, tests/test_dev_coordinator_runner.py, docs/coordination/PERSISTENT_RUNNER.md, docs/handoffs/2026-09-12-persistent-coordinator-runner.md
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "feat(coord): add persistent runner"
---

# Persistent Coordinator runner — first Spec Kit-native implementation

This bridge is execution transport only. The authoritative feature definition is:

- `specs/001-persistent-coordinator-runner/spec.md`
- `specs/001-persistent-coordinator-runner/plan.md`
- `specs/001-persistent-coordinator-runner/research.md`
- `specs/001-persistent-coordinator-runner/tasks.md`
- `specs/001-persistent-coordinator-runner/contracts/runner-config.schema.json`
- `specs/001-persistent-coordinator-runner/quickstart.md`

Read those files first, then `AGENTS.md`, `docs/coordination/TRANSITION_PLAN.md`, and the existing `tools/dev_coordinator/**` implementation/tests. Implement the feature from the Spec Kit artifacts; do not reinterpret the product goal from this bridge text.

## Goal

After one-time operator activation, normal future work must no longer require a terminal command after the user says `Твой ход`.

Future normal flow:

`Architect publishes Spec Kit package + remote target/coord/bridge branches → persistent local runner detects it → prepares managed worktrees → existing one-shot Coordinator launches Cursor once → validates/commits/pushes/verifies → Architect reviews GitHub`.

## Non-negotiable safety boundaries

- Do NOT modify `src/ai_core/**`, provider/runtime/tracing behavior, dependencies, consumer repos, platform-control, old PR #3/#4/#5, release/tag/deployment code.
- Do NOT enable or start a real systemd service during implementation/tests.
- Do NOT trigger hosted CI.
- Do NOT create PRs, merge, tag, release, or deploy.
- Do NOT add automatic claim reclaim.
- Do NOT let the persistent runner make architectural/governance decisions.
- Do NOT scan historical `test/*` bridge branches. Discovery namespace is exactly `coord/bridge/*` by default/config contract.
- Do NOT allow remote prompts to target arbitrary worktree paths. Every managed bridge/executor worktree must be contained under configured `managed_worktree_root`.
- Do NOT target `main`/`master` executor branches.
- Do NOT create remote target/bridge branches from the runner; Architect owns remote branch creation.
- Preserve existing one-shot Coordinator claim, bridge verification, transient cleanup, postconditions, exact-path commit/push, remote verification semantics. Reuse them rather than duplicating them.

## Implementation guidance

Implement the concrete design in `plan.md`. Keep the persistent layer thin and stdlib-only.

Expected modules:

1. `tools/dev_coordinator/runner_config.py`
   - strict JSON config model/parser;
   - reject unknown keys and invalid/non-absolute paths;
   - validate poll interval, exact `coord/bridge/` prefix, repository allowlist, no duplicate clone paths;
   - no new third-party dependency.

2. `tools/dev_coordinator/managed_worktrees.py`
   - safe path containment below managed root;
   - remote branch existence/tip checks;
   - create/reuse bridge and executor worktrees only on exact repo/branch/SHA/clean matches;
   - fail closed for collisions, branch checked out outside managed root, stale worktrees, target main/master, missing/mismatched remote refs;
   - no force/reset/clean destructive shortcuts.

3. `tools/dev_coordinator/runner.py`
   - `--once`, persistent loop, and read-only `--status` modes;
   - poll configured repos, `git fetch origin --prune`, enumerate only `refs/remotes/origin/coord/bridge/*`;
   - read the prompt from the exact remote ref before creating worktrees;
   - parse with existing `parse_next_prompt`;
   - only `EXECUTOR_READY` candidates may proceed;
   - validate target repo allowlist and managed target-worktree containment;
   - process serially;
   - invoke existing one-shot Coordinator (`run_once` or equivalent tested path) rather than reimplement safety/publication;
   - atomically persist terminal `(bridge repo, branch, SHA)` result state under XDG state;
   - unchanged terminal SHA must not relaunch after polling/restart;
   - changed bridge SHA may be reconsidered, but Coordinator claim remains authoritative;
   - fetch/network errors are logged and the persistent service continues later;
   - no automatic claim reclaim.

4. Installer + unit template
   - `scripts/install_dev_coordinator_runner.py`
   - `ops/systemd/ai-core-dev-coordinator-runner.service.in`
   - installer must be idempotent;
   - generate absolute Python/agent/repo/config paths;
   - support explicit `--enable`; without it, write files only;
   - real systemctl invocation must be injectable/mockable in tests;
   - no sudo and no system-level unit.

5. Tests
   - focused runner/config/worktree tests in `tests/test_dev_coordinator_runner.py`;
   - installer tests in `tests/test_dev_coordinator_runner_install.py` if useful/needed;
   - prove historical `test/*` branches are ignored;
   - prove only `coord/bridge/*` is discovered;
   - prove allowlist/path/main-master/dirty/base-SHA/branch-collision fail closed;
   - prove terminal-state idempotency across restart;
   - prove changed bridge SHA is reconsidered without weakening claims;
   - prove network error does not kill future scanning;
   - prove serial execution;
   - prove installer never enables real service in tests.

6. Docs
   - `docs/coordination/PERSISTENT_RUNNER.md`: architecture, safety model, config, status/logging, activation/rollback, normal future workflow;
   - update `docs/coordination/TRANSITION_PLAN.md`: S2A finished; this is the first Spec Kit-native package; bridge becomes transport for new packages, Spec Kit artifacts are authority;
   - update `specs/001-persistent-coordinator-runner/tasks.md` checkboxes honestly to reflect completed work;
   - keep/update quickstart so final commands match the actual implementation.

7. Handoff
   - create `docs/handoffs/2026-09-12-persistent-coordinator-runner.md` with exact branch/base, changed files, tests, risks, rollback, service activation NOT performed, hosted CI NOT requested, and Coordinator-owned publication SHA note.

## Validation

Run locally if shell access is available, without dependency install/resolution and without activating the real service:

1. focused new tests;
2. complete existing Coordinator tests (`tests/test_dev_coordinator.py` plus any existing coordinator-specific suite);
3. `git diff --check`;
4. a fake/temp-repo test proving old `test/*` branches are ignored;
5. installer tests under temporary HOME/fake systemctl.

If a real invariant requires modifying a file outside `allowed_paths`, STOP and report it. Do not broaden scope yourself.

Do not commit or push yourself. Coordinator owns exact-path publication.

Finish with a concise Executor summary and stop.