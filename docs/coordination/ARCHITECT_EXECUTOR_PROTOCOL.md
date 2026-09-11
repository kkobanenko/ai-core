# Architect ↔ Executor protocol (Coordinator v0.2)

## Authoritative channel

`docs/agent-bridge/**` remains the Architect control channel during transition.

## Ownership

| Concern | Owner |
| --- | --- |
| Architecture / prompt | Architect |
| Bounded file edits + required artifacts | Cursor Executor |
| Postcondition validation (real `git status`) | Coordinator |
| Exact-path `git add` / `commit` / `push` / remote verify | Coordinator |
| Hosted CI as merge gate | Humans / policy |

```text
v0.1: Executor owned edit + commit + push
v0.2: Executor owns bounded edits; Coordinator owns publication
```

## Executor rules (v0.2)

Executor **must not** be required to commit/push. If shell/git tools are rejected,
it should still write allowed files and exit; Coordinator inspects the worktree.

## Coordinator publication contract

See runbook for flat metadata fields:

`allowed_paths`, `required_paths`, `publication_commit`, `publication_push`, `commit_message`.

Unexpected paths (example from pilot #1: `uv.lock`) → fail closed, no auto-delete.

## Exactly-once + lock

Unchanged from v0.1.1: persistent claim + `fcntl.flock` singleton under XDG state.

## Non-goals

No daemon loop, no PR creation, no Actions dispatch, no reclaim-by-timeout, no S2A.
