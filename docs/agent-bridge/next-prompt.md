---
coord_version: 1
state: EXECUTOR_READY
prompt_id: main-reconciliation-combined-gate-001
target_repo: kkobanenko/ai-core
target_branch: integration/coordinator-v0.1-to-main-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/integration-coordinator-v0.1-to-main-20260912
base_sha: 67af812452bf0a138adc669ba04a29d576ca2892
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: docs/handoffs/2026-09-12-main-reconciliation-combined-gate.md
required_paths: docs/handoffs/2026-09-12-main-reconciliation-combined-gate.md
publication_commit: true
publication_push: true
commit_message: test(coord): record main reconciliation combined gate
---

# Task: validate main-based Coordinator reconciliation

This is a validation-only reconciliation package. Do not modify product code, Coordinator code, tests, pyproject.toml, specs, or existing docs. The only permitted write is the required handoff evidence file.

## Authority and exact state

- Target branch must be exactly `integration/coordinator-v0.1-to-main-20260912`.
- Target HEAD before any write must be exactly `67af812452bf0a138adc669ba04a29d576ca2892`.
- This integration head combines current `main` (`ac658e514749962b22a7c58643fdec3d5f41f108`, S1 + S2A) with frozen Coordinator transition (`0c7923f8c88b45366afb3bc9a0fb01eb79aedf8d`).
- Hosted CI is forbidden for this validation.

## Required validation

From the target worktree, actually execute:

```bash
PYTHONPATH=. python3.10 -m pytest -q
git diff --check ac658e514749962b22a7c58643fdec3d5f41f108 HEAD
```

Also verify read-only:

```bash
git status --short --branch
git diff --name-only ac658e514749962b22a7c58643fdec3d5f41f108 HEAD
```

Expected structural invariant: reconciliation may add tooling/spec/docs/tests and packaging metadata, but must not introduce any diff under `src/ai_core/**` relative to current main.

## Evidence rules

Only if the commands above were really executed and both required validation commands return exit code 0, create:

`docs/handoffs/2026-09-12-main-reconciliation-combined-gate.md`

The handoff must record:
- exact tested SHA `67af812452bf0a138adc669ba04a29d576ca2892`;
- exact commands executed;
- pytest result including passed/failed count and exit code;
- `git diff --check` exit code;
- confirmation whether any `src/ai_core/**` path differs from main;
- statement that hosted CI was not used;
- statement that no non-handoff file was modified by this package.

After writing the handoff, run `git diff --check ac658e514749962b22a7c58643fdec3d5f41f108 HEAD` again and require exit code 0 before publication.

If shell execution is unavailable, tests fail, diff-check fails, the exact SHA/branch does not match, or any unexpected product-code diff exists: do not claim GREEN and do not modify any file. Report the exact blocker honestly. Do not attempt fixes in this package.
