---
coord_version: 1
state: EXECUTOR_READY
prompt_id: coordinator-live-pilot-3-transient-publication-001
target_repo: kkobanenko/ai-core
target_branch: docs/coordinator-live-pilot-3-20260912
target_worktree: /home/kok4444/projects/ai-core-coordinator-pilot-3-executor
base_sha: f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: docs/handoffs/2026-09-12-coordinator-live-pilot-3.md
required_paths: docs/handoffs/2026-09-12-coordinator-live-pilot-3.md
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "docs: complete coordinator live pilot 3"
---

# Coordinator live pilot #3 — declared transient cleanup + deterministic publication

This is a deliberately harmless documentation-only pilot.

Purpose: prove the full Coordinator v0.2.1 path:

Architect → Coordinator → Cursor bounded edit (+ possible tool-created uv.lock) → declared transient evidence/cleanup → postconditions → exact-path commit → push → remote verification.

## Task

Create exactly one intended work-product file:

`docs/handoffs/2026-09-12-coordinator-live-pilot-3.md`

Do not intentionally create, edit, delete, rename, stage, commit, or push any other repository file.

Do not create or modify `uv.lock` intentionally. If the Cursor/tooling environment creates `uv.lock` as a side effect, leave it untouched; Coordinator owns declared transient classification and cleanup.

The report should be concise (roughly 40–80 lines) and contain:

- title: `Coordinator live pilot #3`;
- prompt id;
- branch and base SHA;
- statement that this is docs-only and does not modify production code;
- statement that Executor owns only bounded file edits;
- statement that Coordinator owns actual git-status validation, declared transient cleanup, exact-path commit/push, and remote verification;
- statement that Executor did not perform commit/push/PR/hosted CI;
- a short section `Expected Coordinator postconditions` listing:
  - required report exists;
  - no undeclared unexpected paths;
  - if `uv.lock` appears, it is handled only as declared transient under the strict Coordinator contract;
  - `git diff --check` must pass;
  - publication success requires local and remote HEAD equality;
- final line exactly: `STATUS: EXECUTOR_EDIT_COMPLETE`.

## Boundaries

Do not modify:

- `README.md`;
- `src/**`;
- `tests/**`;
- `.github/**`;
- `.specify/**`;
- `AGENTS.md`;
- `.cursor/rules/**`;
- `docs/agent-bridge/**` in the executor worktree;
- platform-control;
- consumer repositories;
- active S2 bridge;
- pilot #1 or pilot #2 forensic worktrees/claims;
- PR #3/#4/#5.

Do not start S2A.
Do not run package-management/install commands.
Do not run `uv`, `pip`, `poetry`, or dependency resolution commands.
No PR, no hosted CI, no merge, no tag, no release, no deploy.

You are not responsible for git commit or push. Coordinator owns publication.

When the report file is complete, stop and return a concise summary of the intended file edit only.
