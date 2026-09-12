---
coord_version: 1
state: EXECUTOR_READY
prompt_id: persistent-coordinator-self-update-spec-001
target_repo: kkobanenko/ai-core
target_branch: spec/002-persistent-coordinator-self-update-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/spec-002-persistent-coordinator-self-update-20260912
base_sha: e41019b5f63589bc450eb5f29230ab7df027eabf
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: specs/002-persistent-coordinator-self-update/spec.md, specs/002-persistent-coordinator-self-update/plan.md, specs/002-persistent-coordinator-self-update/research.md, specs/002-persistent-coordinator-self-update/tasks.md, specs/002-persistent-coordinator-self-update/quickstart.md, docs/handoffs/2026-09-12-persistent-coordinator-self-update-spec.md
required_paths: specs/002-persistent-coordinator-self-update/spec.md, specs/002-persistent-coordinator-self-update/plan.md, specs/002-persistent-coordinator-self-update/research.md, specs/002-persistent-coordinator-self-update/tasks.md, specs/002-persistent-coordinator-self-update/quickstart.md, docs/handoffs/2026-09-12-persistent-coordinator-self-update-spec.md
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "spec(coord): define safe persistent self-update"
---

# Spec Kit package 002 — Persistent Coordinator self-update

This is a SPEC-ONLY package. Do not implement production code, installer changes, systemd units, scripts, or tests in this package.

## Goal

Close the last manual-maintenance gap in the persistent Coordinator architecture: after Architect review/merge advances the authoritative Coordinator transition branch on GitHub, the user's local Coordinator checkout and persistent `systemd --user` runner should safely advance to that reviewed transition head without requiring the user to run `git fetch/merge` and `systemctl restart` manually.

The current authoritative tooling branch is:
`chore/coordinator-transition-v0.1-20260911`.

This capability is tooling-plane only. It must not authorize or alter `src/ai_core/**`, providers, runtime routing, consumers, platform-control governance, releases, or deployments of product services.

## Required architecture decisions to capture

Design a conservative, fail-closed self-update mechanism, preferably as a separate `systemd --user` updater service + timer rather than having the runner mutate its own checkout inline.

The specification/plan must cover at least:

1. **Authority and update source**
   - Only the configured reviewed transition branch is eligible as update source.
   - No automatic merge of feature branches or PRs; Architect/GitHub merge remains the decision boundary.
   - No main/master target and no arbitrary ref input.

2. **Git safety**
   - `git fetch origin` is allowed.
   - Local Coordinator checkout must be the expected canonical repository, expected transition branch, and clean.
   - Update only by strict fast-forward semantics (`git merge --ff-only` or equivalent verified fast-forward).
   - No force, reset, clean, checkout switching, stash, rebase, branch deletion, or auto conflict resolution.
   - Diverged/dirty/wrong-origin/wrong-branch states fail closed and are reported; they are never repaired automatically.

3. **Do not interrupt an active work package**
   - Coordinate with the existing Coordinator process lock (or an equally deterministic shared lock).
   - If a package is actively executing/publicating, updater must skip and retry later rather than stop/restart the runner mid-package.
   - Define the race-safe sequence for lock acquisition, runner stop/restart, and local fast-forward.

4. **Service supervision**
   - Persistent runner remains supervised by `systemd --user`.
   - Updater should be separately supervised/scheduled (timer/service) with a conservative cadence, e.g. around 60 seconds; exact default must be documented, configurable if justified, and never faster than needed.
   - Restart runner only after a successful local head change.
   - No restart when already at remote head.
   - A failed update must leave a diagnosable state and must not cause a restart loop.

5. **Installer / activation**
   - Extend the existing idempotent installer design rather than requiring ad-hoc shell setup.
   - Existing config paths and runner installation remain compatible.
   - There will be one final operator activation/update after implementation is reviewed; after that, future reviewed transition updates should not require per-update terminal commands.
   - Clearly document this bootstrap boundary.

6. **Observability and state**
   - Structured logs/status should expose current local Coordinator head, remote reviewed head when known, last update attempt/result, and reason for fail-closed/skip.
   - Do not store secrets.

7. **Testing**
   - Unit/integration tests with fake git/systemctl/lock behavior for: already-current no-op; clean fast-forward; dirty checkout refusal; diverged refusal; wrong branch/origin refusal; active Coordinator lock causes skip/retry; successful update triggers exactly one runner restart; failed/no-op update triggers no restart; installer idempotence.
   - No live systemd mutation in tests.
   - Hosted CI remains forbidden for this package unless separately authorized.

8. **Rollback**
   - Define disabling the updater timer/service while leaving the persistent runner usable on its last known-good local checkout.
   - Manual one-shot Coordinator remains emergency fallback.

## Spec Kit artifacts

Create:
- `specs/002-persistent-coordinator-self-update/spec.md`
- `specs/002-persistent-coordinator-self-update/plan.md`
- `specs/002-persistent-coordinator-self-update/research.md`
- `specs/002-persistent-coordinator-self-update/tasks.md`
- `specs/002-persistent-coordinator-self-update/quickstart.md`
- `docs/handoffs/2026-09-12-persistent-coordinator-self-update-spec.md`

The handoff must record exact branch/base, that this package is specification-only, open design risks, and the proposed next implementation package boundaries.

Do not modify `.specify/memory/constitution.md`; it is still unratified. Operative governance remains `AGENTS.md`, existing transition documentation, and platform-control authority.

Do not implement. Do not run hosted CI. Do not create PRs, merge, release, tag, deploy, or alter systemd on the host.

Do not commit or push yourself. Coordinator owns exact-path commit/push/remote verification.

Finish with a concise Executor summary and stop.
