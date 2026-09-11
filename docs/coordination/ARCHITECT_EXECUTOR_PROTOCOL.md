# Architect ↔ Executor protocol (transitional)

## Authoritative channel

Until Architect explicitly retires it, the control channel is:

```text
docs/agent-bridge/
  next-prompt.md      ← Architect / operator instruction (active)
  latest-report.md    ← Executor report (active)
  prompts/            ← archived instructions
  reports/            ← archived reports
  README.md           ← bridge conventions
```

Governance truth still lives in `AGENTS.md`, `.cursor/rules/**`, and
platform-control. Bridge files are coordination artifacts; on conflict,
governance/evidence wins and the conflict is recorded in the next report.

## Current (legacy) loop

1. Architect writes `next-prompt.md`.
2. Human starts Cursor Executor with that prompt.
3. Executor works, updates `latest-report.md`, archives artifacts.
4. Architect reviews; may set `# WAIT` or a new prompt.
5. Human says «Твой ход» when Architect should continue.

## Transitional loop (Coordinator v0.1)

1. Architect writes `next-prompt.md` (legacy WAIT **or** Coordinator metadata).
2. Human runs Coordinator (`--mode shadow` first; `--mode launch` when ready).
3. Coordinator:
   - reads bridge state;
   - if not `EXECUTOR_READY` → prints decision and exits (no Cursor);
   - if `EXECUTOR_READY` and safety OK → launches Cursor **once**;
   - observes exit code → **stops** (no autonomous loop).
4. Executor continues the **same** report/archive convention.
5. When bridge returns to WAIT / ARCHITECT_REVIEW, Coordinator does nothing
   until the human asks again («Твой ход»).

## Coordinator metadata (future prompts)

Optional YAML front matter (backwards compatible):

```yaml
---
coord_version: 1
state: EXECUTOR_READY
prompt_id: s2a-implementation-001
target_repo: kkobanenko/ai-core
target_branch: feat/...
target_worktree: /path/to/isolated/worktree
base_sha: ...
hosted_ci: forbidden
max_executor_runs: 1
---
```

### Required v0.1 states

| State | Coordinator behavior |
| --- | --- |
| `WAIT` | Do nothing, exit cleanly |
| `EXECUTOR_READY` | May launch once (launch mode + safety) |
| `EXECUTOR_RUNNING` | No launch (already running / reserved) |
| `ARCHITECT_REVIEW` | No launch |
| `HUMAN_REQUIRED` | No launch |
| `PAUSED` | No launch |
| `DONE` | No launch |

Legacy files **without** front matter:

- `# WAIT` heading → treat as `WAIT` (zero mutations).
- Anything else → **fail closed** (do not invent EXECUTOR_READY).

Unknown or inconsistent metadata → **fail closed**.

## Ownership today vs later

| Concern | v0.1 owner | Possible v0.2 owner |
| --- | --- | --- |
| Decide whether Executor may start | Coordinator | Coordinator |
| Start Cursor | Coordinator (launch mode) | Coordinator |
| Implement code / follow prompt | Executor | Executor |
| Commit / push / publish report | Executor (legacy) | Coordinator (candidate) |
| Hosted CI as merge gate | Humans / policy | unchanged |
| Architecture decisions | Architect / human | never Coordinator |

## Explicit non-goals

Coordinator must not:

- reinterpret Architect technical requirements;
- create PRs or trigger hosted CI for iteration;
- switch the primary AI Core checkout silently;
- stash/reset/clean unknown dirty files;
- run endless loops.
