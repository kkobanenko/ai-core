---
coord_version: 1
state: EXECUTOR_READY
prompt_id: coordinator-file-level-untracked-status-hotfix-001
target_repo: kkobanenko/ai-core
target_branch: fix/coordinator-file-level-untracked-status-20260912
target_worktree: /home/kok4444/projects/ai-core-coordinator-file-status-hotfix-executor
base_sha: c3a4dbeade14b0711d6f6686c0ab99a5df3d6a74
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: tools/dev_coordinator/publication.py, tools/dev_coordinator/transient.py, tests/test_dev_coordinator.py
required_paths: tools/dev_coordinator/publication.py, tools/dev_coordinator/transient.py, tests/test_dev_coordinator.py
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "fix(coord): enumerate untracked files in postconditions"
---

# Coordinator hotfix — file-level untracked status

This is a narrow maintenance package required to finish the already in-flight S2A old bridge cycle.
Do NOT start S2A implementation here.
Do NOT modify platform-control or any consumer repository.
Do NOT create PRs, tags, releases, deployments, or hosted CI runs.

## Problem proven by live R5

A valid Executor run created the exact allowed file:

`docs/handoffs/2026-09-12-ai-core-s2a-governance-reconciliation.md`

but Coordinator postconditions observed only:

`docs/handoffs/`

because ordinary `git status --porcelain` may collapse untracked directories.
This caused a false `POSTCONDITION_FAILED` even though the exact file was allowed.

Coordinator exact-path publication requires file-level untracked enumeration.

## Required implementation

1. In `tools/dev_coordinator/publication.py`, make postcondition status collection enumerate all untracked files, e.g. with:

`git status --porcelain --untracked-files=all`

Preserve exact-path allowlist semantics and all existing fail-closed behavior.
Do NOT weaken allowlists to directory-prefix matching.
Do NOT permit directory staging.
Do NOT replace exact-path `git add -- <paths>` with `.`, `-A`, globbing, or recursive staging.

2. In `tools/dev_coordinator/transient.py`, use the same file-level untracked status form anywhere porcelain output is later interpreted as exact paths:
- prelaunch transient snapshot;
- post-executor transient classification;
- post-cleanup re-verification.

This keeps nested transient exact-path behavior consistent with publication.

3. In `tests/test_dev_coordinator.py`, add regression coverage proving at minimum:
- a nested untracked file such as `docs/handoffs/report.md` is surfaced as that exact path, not `docs/handoffs/`;
- if that exact file is in `allowed_paths`, postconditions pass;
- an undeclared sibling remains unexpected/fail-closed;
- exact-path publication behavior remains unchanged;
- transient handling still requires declared exact files and remains fail-closed.

Use existing test style/helpers. Avoid broad refactors.

## Validation

Run locally:

- focused Coordinator tests;
- full test suite if practical;
- `python -m compileall tools/dev_coordinator`;
- `git diff --check`.

No hosted CI.

## Scope guard

Allowed changes are ONLY:
- `tools/dev_coordinator/publication.py`
- `tools/dev_coordinator/transient.py`
- `tests/test_dev_coordinator.py`

Do not create documentation/handoff files in this package; the current Coordinator version cannot safely publish a new untracked nested doc until this fix is applied.

Do not commit or push yourself. Coordinator owns deterministic publication.

Finish with a concise summary and stop.