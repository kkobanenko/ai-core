# Coordinator runbook (v0.1.1 LIVE-PILOT-READY)

## Location

```text
tools/dev_coordinator/
```

Not under `src/ai_core/`. Stdlib only. State/locks **outside** the git tree.

## Modes

| Flag | Behavior |
| --- | --- |
| `--mode shadow` (**default**) | Read bridge; report what would happen. No Cursor, no claim write, no commits/push. |
| `--mode launch` | May launch Cursor **once** iff `EXECUTOR_READY`, safety OK, process lock free, and **new** claim acquired. |
| `--once` | One evaluation and exit (default). No daemon/polling. |

## Exactly-once claim

Identity (minimum):

```text
prompt_id | target_repo | target_branch | base_sha | SHA256(full next-prompt.md)
```

Stored under:

```text
${AI_CORE_COORDINATOR_STATE_DIR:-${XDG_STATE_HOME:-~/.local/state}/ai-core-dev-coordinator}/claims/<sha256(identity)>.json
```

Created with `O_CREAT|O_EXCL` **before** Executor start.

If claim already exists → **no launch** → `HUMAN_REQUIRED` (prefer false negative).
**No automatic reclaim / timeout** in v0.1.1. Human/Architect must decide recovery after crash mid-execution.

## Process lock (singleton)

```text
…/ai-core-dev-coordinator/locks/coordinator.lock
```

`fcntl.flock` exclusive, non-blocking. Two Coordinator processes cannot both launch.

## Bridge source

Launch **requires** `--bridge-worktree PATH`.

Checks:

1. `--bridge-prompt` is inside that worktree;
2. worktree is a git worktree of the expected repo;
3. branch + local HEAD determinable;
4. `git ls-remote origin refs/heads/<branch>` matches local HEAD (launch).

Do not point `--bridge-prompt` at an arbitrary file outside the declared bridge worktree.

## Target repository

`target_repo` is verified against `git remote get-url origin` in the **executor** worktree.

Supported URL forms:

```text
git@github.com:OWNER/REPO.git
https://github.com/OWNER/REPO.git
https://github.com/OWNER/REPO
ssh://git@github.com/OWNER/REPO.git
```

Mismatch → `HUMAN_REQUIRED`, no launch.

## Governance source

Authoritative governance for the Executor prompt is loaded from **`executor_worktree`**:

```text
<executor_worktree>/AGENTS.md
<executor_worktree>/.cursor/rules/**
```

Not from a stale primary checkout.

## Dirty override

```text
--mode launch --allow-dirty   → FAIL CLOSED (v0.1.1)
```

Live launch always requires a clean declared Executor worktree. `--allow-dirty` is not for unattended live use.

## Typical commands

### Shadow (safe default)

```bash
PYTHONPATH=. python3.10 -m tools.dev_coordinator --mode shadow --once --json \
  --bridge-worktree /path/to/active-bridge-worktree \
  --bridge-prompt /path/to/active-bridge-worktree/docs/agent-bridge/next-prompt.md \
  --repo-root /path/to/primary-or-transition \
  --executor-worktree /path/to/declared-executor-worktree
```

### Future live pilot (DO NOT run until Architect authorizes)

```bash
PYTHONPATH=. python3.10 -m tools.dev_coordinator --mode launch --once --json \
  --bridge-worktree <ACTIVE_BRIDGE_WORKTREE> \
  --bridge-prompt <ACTIVE_BRIDGE_WORKTREE>/docs/agent-bridge/next-prompt.md \
  --executor-worktree <DECLARED_TARGET_WORKTREE> \
  --repo-root <PRIMARY_OR_TRANSITION> \
  --state-dir "${XDG_STATE_HOME:-$HOME/.local/state}/ai-core-dev-coordinator" \
  --agent-bin agent
```

Requires metadata `state: EXECUTOR_READY` with full required fields and a clean matching worktree.
Same prompt identity will not launch twice.

## Recovery after stale claim

1. Inspect `…/claims/<hash>.json`.
2. Confirm whether Executor actually ran / what git state remains.
3. Architect decides: leave blocked, or **manually** remove that claim file after review.
4. Never auto-delete claims from Coordinator v0.1.1.

## Local tests

```bash
PYTHONPATH=.:src python3.10 -m pytest -q tests/test_dev_coordinator.py
PYTHONPATH=.:src python3.10 -m pytest -q
python3.10 -m compileall -q src tools
git diff --check
```
