# Coordinator runbook (v0.1)

## Location

```text
tools/dev_coordinator/
```

Not under `src/ai_core/`. Development tooling only. Stdlib + local git/agent CLI.

## Modes

| Flag | Behavior |
| --- | --- |
| `--mode shadow` (**default**) | Read bridge; report what would happen. No Cursor, no commits, no push, no GitHub writes. |
| `--mode launch` | Same evaluation; may launch Cursor **once** iff `state=EXECUTOR_READY` and safety passes. |
| `--once` | One evaluation and exit (default; endless loops are not implemented). |

## Typical commands

From an isolated worktree or any checkout that can **read** the active bridge
file (copy path or checkout that contains it):

```bash
# Safe default — zero mutations
PYTHONPATH=. python3 -m tools.dev_coordinator --mode shadow --once --json

# Point at an explicit bridge file (e.g. from active bridge worktree)
PYTHONPATH=. python3 -m tools.dev_coordinator \
  --mode shadow --once --json \
  --bridge-prompt /path/to/docs/agent-bridge/next-prompt.md \
  --repo-root /path/to/ai-core-primary \
  --executor-worktree /path/to/declared-executor-worktree

# Launch only when metadata says EXECUTOR_READY and checks pass
PYTHONPATH=. python3 -m tools.dev_coordinator \
  --mode launch --once \
  --bridge-prompt ... \
  --repo-root ... \
  --executor-worktree ...
```

Verified Cursor CLI shape (local `agent --help`, 2026.08.04):

```text
agent --print --workspace <path> --trust <prompt>
```

## Safety gates before launch

Coordinator refuses launch (maps to human attention) when:

- bridge missing / unparseable / unknown state;
- `max_executor_runs != 1`;
- declared `target_branch` / `target_worktree` / `base_sha` missing or mismatched;
- worktree dirty (unless explicit `--allow-dirty`, debug only);
- another Executor lock is held (when wired);
- primary checkout would be silently switched without declaration.

It never stash/reset/cleans unknown files.

## Legacy WAIT

Current active bridge style:

```markdown
# WAIT
...
```

Shadow or launch against that file must produce **no mutations** and no Cursor
start. Exit cleanly.

## After Executor exits

Coordinator v0.1 **stops**. It does not:

- poll for a new prompt;
- commit;
- push;
- open a PR;
- wait for GitHub Actions.

Human / Architect resume with «Твой ход» when ready.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Clean stop (WAIT, shadow decision, successful launch observation) |
| 2 | Fail closed / `HUMAN_REQUIRED` |
| other | Propagated non-zero Executor exit when launch occurred |

## Local tests

```bash
PYTHONPATH=.:src python3 -m pytest -q tests/test_dev_coordinator.py
PYTHONPATH=.:src python3 -m pytest -q
python3 -m compileall -q src tools
git diff --check
```
