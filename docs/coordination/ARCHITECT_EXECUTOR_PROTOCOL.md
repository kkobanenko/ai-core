# Architect ↔ Executor protocol (transitional, Coordinator v0.1.1)

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

Governance truth still lives in `AGENTS.md`, `.cursor/rules/**` (of the
**executor worktree**), and platform-control.

## Transitional loop (v0.1.1)

1. Architect writes `next-prompt.md` (legacy `# WAIT` **or** Coordinator metadata).
2. Human runs Coordinator (`shadow` first; `launch` only when authorized).
3. Coordinator:
   - verifies bridge **source** (`--bridge-worktree` + prompt path + git + remote tip);
   - evaluates state;
   - for `EXECUTOR_READY`: process lock → **atomic claim** → launch Cursor once;
   - stops (no loop).
4. Executor continues the same report/archive convention.
5. Re-invocation with the **same** ready identity does **not** launch again.

## Coordinator metadata

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

### Required for `EXECUTOR_READY`

All of: `coord_version`, `state`, `prompt_id`, `target_repo`, `target_branch`,
`target_worktree`, `base_sha`, `hosted_ci`, `max_executor_runs` — **non-empty**.

Duplicate YAML keys → parse error (fail closed).

### Other states

`WAIT` / `DONE` / … may use a shorter metadata block (`coord_version` + `state`).

Legacy `# WAIT` without front matter → no action, exit cleanly.

## Ownership

| Concern | v0.1.1 owner |
| --- | --- |
| Start gate + exactly-once claim + process lock | Coordinator |
| Implement / commit / push / publish report | Executor (legacy) |
| Architecture decisions | Architect / human |
| Hosted CI as merge gate | Humans / policy — never iteration |

## Explicit non-goals (still)

No polling daemon, no automatic Architect, no PR/Actions ownership, no systemd,
no reclaim-by-timeout, no commit/push takeover (candidate for v0.2).
