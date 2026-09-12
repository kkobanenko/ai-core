# Implementation Plan: Persistent Coordinator Runner

**Branch**: `feat/001-persistent-coordinator-runner-20260912` | **Date**: 2026-09-12 | **Spec**: `specs/001-persistent-coordinator-runner/spec.md`

**Input**: Feature specification from `/specs/001-persistent-coordinator-runner/spec.md`

## Summary

Add a local persistent runner around the already-tested one-shot Coordinator. The runner discovers only new `coord/bridge/*` refs in configured repositories, validates package metadata and managed paths, prepares exact bridge/executor worktrees, and delegates execution/publication to the existing Coordinator. A `systemd --user` service keeps the runner alive across terminal closure and ordinary login/session restarts. Spec Kit artifacts are authoritative; `docs/agent-bridge/next-prompt.md` remains transport only.

## Technical Context

**Language/Version**: Python 3.10

**Primary Dependencies**: Python stdlib; existing `tools.dev_coordinator` package; git CLI; systemd user manager; existing Cursor `agent` executable

**Storage**: Local JSON config and JSON state under XDG config/state directories; existing Coordinator claim/log state

**Testing**: pytest with fake git/runner harnesses plus bounded local smoke test

**Target Platform**: User workstation, Linux with systemd user services

**Project Type**: developer automation CLI/service

**Performance Goals**: discover valid packages within 30 seconds at default 15-second polling; negligible idle CPU; one active package at a time

**Constraints**: fail closed; no force; no automatic claim reclaim; no hosted-CI triggering; no PR merge/tag/release/deploy; no target main/master; no arbitrary worktree paths; no new third-party Python dependency

**Scale/Scope**: initial bridge allowlist contains ai-core and platform-control only; tens of remote refs; single operator workstation

## Constitution Check

The `.specify/memory/constitution.md` file is still a placeholder and is not a ratified project constitution. Operative gates therefore come from `AGENTS.md`, platform-control governance, and `docs/coordination/TRANSITION_PLAN.md`.

Pre-design gates:

- PASS — deterministic Python remains responsible for verification/publication; LLM/Executor does not gain authority.
- PASS — persistent runner launches only already-authorized packages and does not make architectural decisions.
- PASS — existing one-shot Coordinator safety/claim/publication logic is reused rather than reimplemented.
- PASS — old bridge branches are isolated by new `coord/bridge/*` discovery namespace.
- PASS — shared ai-core runtime/provider/tracing code is outside scope.
- PASS — failures remain fail-closed and visible.

Post-design re-check: no identified gate violation requires a complexity exception.

## Architecture

### Control flow

```text
Architect / Spec Kit
  ├─ creates target remote branch at exact base SHA
  └─ creates coord/bridge/<package> remote branch with EXECUTOR_READY prompt
                         ↓
              Persistent runner (poll)
                         ↓
       fetch + strict candidate filtering
                         ↓
     managed bridge/executor worktree prep
                         ↓
         existing dev_coordinator.run_once
                         ↓
      Cursor Executor → postconditions →
      transient cleanup → exact commit/push →
      remote verification
                         ↓
           local terminal runner state
                         ↓
               Architect review
```

### Discovery

For each configured repository clone:

1. run `git fetch origin --prune`;
2. enumerate remote refs under `refs/remotes/origin/coord/bridge/*` only;
3. obtain remote bridge SHA and read `docs/agent-bridge/next-prompt.md` from that exact remote ref with `git show`;
4. parse using existing `parse_next_prompt`;
5. ignore WAIT/DONE and malformed non-ready candidates; record fail-closed diagnostics where appropriate;
6. skip a `(repo, branch, sha)` already stored with a terminal runner result;
7. process ready candidates serially.

### Managed worktrees

Runner config has one `managed_worktree_root`. Every package prompt must declare `target_worktree` below this root. Bridge worktree path is runner-derived below the same root. A helper module performs:

- canonical path containment checks;
- remote ref existence checks;
- local branch collision checks;
- safe `git worktree add --track -b <branch> ... origin/<branch>` for branches not yet local;
- exact reuse only when an existing managed worktree is clean and matches expected repo, branch and SHA;
- fail closed if the branch is checked out outside managed root or an existing path is inconsistent.

No automatic worktree deletion is required in v1; explicit cleanup can be a later package. This preserves forensic evidence.

### Runner state

Use a JSON file under `${XDG_STATE_HOME:-~/.local/state}/ai-core-dev-coordinator/runner-state.json`, written atomically by temp-file + `os.replace`. Key packages by a stable string containing bridge repo, branch and SHA. Store prompt ID, target repo/branch, lifecycle status, timestamps, result/log path and publication SHA when available.

Terminal runner statuses include at minimum:

- `SUCCESS`
- `FAIL_CLOSED`
- `HUMAN_REQUIRED`
- `EXECUTOR_FAILED`
- `PUBLICATION_FAILED`

Coordinator `RunResult.final_status` remains authoritative for execution result classification.

### Configuration

JSON file under `${XDG_CONFIG_HOME:-~/.config}/ai-core-dev-coordinator/runner.json`:

```json
{
  "poll_interval_seconds": 15,
  "coordinator_repo_root": "/home/kok4444/projects/ai-core-coordinator-transition",
  "managed_worktree_root": "/home/kok4444/projects/.coordinator-worktrees",
  "agent_bin": "/absolute/path/to/agent",
  "bridge_prefix": "coord/bridge/",
  "repositories": {
    "kkobanenko/ai-core": "/home/kok4444/projects/ai-core",
    "kkobanenko/platform-control": "/home/kok4444/projects/platform-control"
  }
}
```

Parser must reject unknown top-level keys, invalid intervals, non-absolute/nonexistent configured repo paths, duplicate paths, unsupported bridge prefix, and coordinator repo root mismatch where safety requires it.

### Service installation

Add an idempotent installer command/script that:

1. resolves absolute Python 3.10 and `agent` paths;
2. writes runner config with current known repository paths;
3. writes a generated `~/.config/systemd/user/ai-core-dev-coordinator-runner.service`;
4. runs `systemctl --user daemon-reload` and `systemctl --user enable --now ai-core-dev-coordinator-runner.service` only when explicit `--enable`/install command is invoked by the operator;
5. prints status/journal commands and does not request sudo.

Activation is a one-time operator action after Architect review/merge. No package implementation test may enable the live service implicitly.

## Project Structure

### Documentation (this feature)

```text
specs/001-persistent-coordinator-runner/
├── spec.md
├── plan.md
├── research.md
├── quickstart.md
├── contracts/
│   └── runner-config.schema.json
└── tasks.md
```

### Source Code

```text
tools/dev_coordinator/
├── runner.py                # service loop + scan orchestration
├── runner_config.py         # strict JSON config
├── managed_worktrees.py     # safe managed worktree preparation
└── ... existing one-shot Coordinator modules unchanged where possible

scripts/
└── install_dev_coordinator_runner.py

ops/systemd/
└── ai-core-dev-coordinator-runner.service.in

tests/
├── test_dev_coordinator_runner.py
└── test_dev_coordinator_runner_install.py

docs/coordination/
└── PERSISTENT_RUNNER.md
```

**Structure Decision**: Keep persistent orchestration as a thin layer adjacent to `tools.dev_coordinator`; do not fold it into runtime `src/ai_core` and do not rewrite the proven one-shot Coordinator.

## Validation Strategy

1. Unit tests for strict config parsing and path containment.
2. Fake-git tests for branch discovery limited to `coord/bridge/*`.
3. Worktree tests for create/reuse/collision/outside-root cases.
4. Runner integration tests using fake Coordinator invoker proving serial execution and terminal-state idempotency.
5. Restart test: reload state then rescan same SHA → zero launches.
6. Network/fetch failure test → service loop survives and later scan can proceed.
7. Installer tests against temporary HOME without invoking real systemctl unless a fake runner is injected.
8. Full existing Coordinator tests to prove no regression.
9. Manual bounded smoke before activation: `runner --once` against a harmless test package.
10. Operator activation only after exact-head Architect review.

## Rollback

Before activation: revert/drop feature branch; no workstation service exists.

After activation: `systemctl --user disable --now ai-core-dev-coordinator-runner.service`, remove/retain local config/state as desired, then revert the feature commit if needed. Existing manual one-shot Coordinator remains available throughout rollback.

## Complexity Tracking

No constitution violation or required complexity exception identified.
