# GitHub Actions quota policy (AI Core)

## Policy statement

**Hosted CI is a final merge-candidate gate, not an iteration mechanism.**

Normal validation for Coordinator and day-to-day Executor work is **local**:

```bash
python -m pytest -q
python -m compileall -q src tools
git diff --check
```

## Current workflow triggers (verified 2026-09-11)

`.github/workflows/ci.yml`:

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

Therefore:

| Action | Hosted CI? |
| --- | --- |
| Push feature branch (not `main`) | No |
| Open / synchronize PR targeting `main` | **Yes** |
| Push to `main` | **Yes** |
| `workflow_dispatch` | Not configured (do not add for iteration) |

If remote workflow configuration changes so that feature-branch pushes start
Actions, **stop** and report to Architect before pushing again.

## Forbidden for Coordinator v0.1 / this transition task

- Create PRs to burn CI minutes for iteration
- Temporarily retarget unrelated PRs to `main` to run CI
- `workflow_dispatch` / rerun Actions for development loops
- Push to `main`
- Change CI triggers or add new hosted workflows for this tooling

## Allowed

- Read existing hosted CI status as **informational** evidence
- Push a feature branch after local green, when triggers still exclude it
- Use local pytest / compileall / diff --check as the development gate

## Merge-candidate practice

1. Iterate locally on a feature branch.
2. Only when Architect authorizes a merge-candidate review, open a PR (or use
   an explicitly authorized CI path).
3. Treat green hosted CI as a **merge gate**, not a substitute for local runs.
