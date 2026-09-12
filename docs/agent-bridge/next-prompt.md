---
coord_version: 1
state: EXECUTOR_READY
prompt_id: persistent-coordinator-self-update-review-fix4-001
target_repo: kkobanenko/ai-core
target_branch: feat/002-persistent-coordinator-self-update-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/feat-002-persistent-coordinator-self-update-20260912
base_sha: b26de225a7d7d7c24bc7ef182e1eea57908ab896
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: scripts/install_dev_coordinator_runner.py, tests/test_dev_coordinator_updater_install.py, tests/test_dev_coordinator_runner_install.py, docs/coordination/PERSISTENT_RUNNER.md, specs/002-persistent-coordinator-self-update/tasks.md, docs/handoffs/2026-09-12-persistent-coordinator-self-update-impl.md
required_paths: scripts/install_dev_coordinator_runner.py, tests/test_dev_coordinator_updater_install.py
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "fix(coord): make updater bootstrap restart-safe"
---

# Architect review-fix 4 — restart-safe one-time updater activation

## Context

Exact reviewed head: `b26de225a7d7d7c24bc7ef182e1eea57908ab896`.

Self-updater recovery/concurrency logic is now substantially hardened. Exact bootstrap review found one remaining activation blocker in `scripts/install_dev_coordinator_runner.py`:

- the workstation already has an active persistent runner process started from older bootstrap code;
- installer rewrites runner unit/config and calls `systemctl --user enable --now ai-core-dev-coordinator-runner.service` when `--enable` is used;
- `enable --now` does not guarantee replacement of an already-active process after the underlying Coordinator checkout/unit content changed;
- installer can then enable the updater timer;
- if the old runner keeps running, it does not participate in the new maintenance shared gate, so first self-update coordination is not safe.

The one-time updater activation must therefore prove that the persistent runner process has been restarted onto the newly reviewed code before the updater timer becomes active.

## Required repair

Implement a deterministic, fail-closed activation sequence for `--enable-updater`.

### Activation ordering

When updater activation is requested, the installer MUST ensure the runner service is enabled/running on the newly installed/reviewed unit/code before enabling the updater timer.

A safe sequence is:

1. write runner config/unit and updater config/service/timer files;
2. `systemctl --user daemon-reload`;
3. ensure runner service is enabled as appropriate;
4. execute an explicit `systemctl --user restart ai-core-dev-coordinator-runner.service` (or an equivalent operation that deterministically replaces an already-running old process);
5. only if runner restart succeeds, enable/start `ai-core-dev-coordinator-updater.timer`;
6. if runner restart fails, fail closed and do NOT enable/start the updater timer.

Do not rely on `enable --now` alone as proof that an already-running runner has re-execed new code.

### CLI semantics

Make the activation contract unambiguous and safe.

Preferred simple contract: `--enable-updater` requires/implicitly guarantees runner activation as part of the same installer transaction. It must never produce `updater_enabled=true` while the runner has not been successfully restarted on the current installed version.

You may either:

- require `--enable` together with `--enable-updater` and reject unsafe combinations before systemctl mutation; or
- define `--enable-updater` to also ensure/enable/restart runner itself.

Choose the simpler deterministic behavior and document it clearly. Preserve existing runner-only `--enable` behavior unless safety requires a narrow adjustment.

### Failure ordering

- `daemon-reload` failure -> no timer enable;
- runner enable/restart failure -> no timer enable;
- updater timer enable failure -> report installer failure; runner may remain active on new reviewed code;
- never disable/reset/delete services automatically as recovery;
- no loops.

Avoid redundant timer activation or multiple runner restarts in one invocation.

## Regression tests

Use injected fake `systemctl_runner`; tests must not touch live systemd.

At minimum prove:

1. updater bootstrap with an already-active conceptual runner emits an explicit runner `restart` before updater timer `enable --now`;
2. exact call ordering is deterministic: daemon-reload / runner enable as designed / runner restart / timer enable;
3. runner restart failure raises/fails installer and timer enable is never called;
4. daemon-reload failure prevents both restart/timer activation as appropriate;
5. timer enable failure is surfaced and does not trigger a retry loop;
6. runner-only `--enable` behavior remains compatible;
7. write-only install without activation flags invokes no live systemctl mutations;
8. repeated/idempotent installation still produces valid unit/config contents and at most the intended single runner restart per updater activation invocation.

Do not weaken existing installer assertions; update them to the deliberate new ordering where necessary.

## Scope boundaries

Do not change:

- updater transaction/recovery implementation unless an installer test proves a direct integration defect;
- locks/runner discovery/bridge publication;
- `src/ai_core/**`;
- platform-control or consumer repositories;
- hosted CI, release, tag, deployment.

Do not activate live systemd from Executor.

Update `docs/coordination/PERSISTENT_RUNNER.md`, Spec Kit task bookkeeping and implementation handoff with the restart-safe bootstrap contract and tests actually run. If shell execution is unavailable, say so explicitly and do not claim tests passed.

Finish with concise Executor summary and stop. Coordinator owns publication.
