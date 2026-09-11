# Coordinator runbook (v0.2 deterministic publication)

## Ownership split

```text
v0.1:
  Executor owned edit + commit + push

v0.2:
  Executor owns bounded edits / artifacts / local checks
  Coordinator owns postcondition validation + exact-path commit + push + remote verify
```

`executor_exit_code == 0` means only `EXECUTOR_PROCESS_EXITED_ZERO`, **not** work-package success.

## Location

```text
tools/dev_coordinator/
```

State/locks outside git:

```text
${AI_CORE_COORDINATOR_STATE_DIR:-${XDG_STATE_HOME:-~/.local/state}/ai-core-dev-coordinator}/
  claims/
  locks/
  logs/          # capped executor stdout/stderr tails
```

## Publication metadata (flat, no PyYAML lists)

```yaml
---
coord_version: 1
state: EXECUTOR_READY
prompt_id: ...
target_repo: kkobanenko/ai-core
target_branch: docs/...
target_worktree: /path/to/executor
base_sha: ...
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: docs/handoffs/report.md
required_paths: docs/handoffs/report.md
publication_commit: true
publication_push: true
commit_message: "docs: complete coordinator live pilot 2"
---
```

Multiple paths: comma-separated (`a.md, b.md`). `required_paths` ⊆ `allowed_paths`.

## After Executor exit

1. `git status --porcelain` — authoritative changed paths
2. Unexpected path ∉ `allowed_paths` → `POSTCONDITION_FAILED`, no commit/push
3. Missing `required_paths` → `POSTCONDITION_FAILED`
4. `git diff --check` → must pass
5. If publication requested and green:
   - `git add -- <exact paths only>` (**never** `git add .` / `-A`)
   - `git commit -m "<commit_message>"`
   - `git push origin HEAD:refs/heads/<target_branch>` (never `main`, never force)
   - `git ls-remote` must equal local HEAD

## Result fields

```text
executor_exit_code
postconditions_ok
unexpected_paths
required_paths_ok
validation_ok
commit_created
local_head
push_attempted
remote_head
publication_verified
final_status
elapsed_seconds
executor_stdout_tail / executor_stderr_tail (<= 32 KiB each)
executor_log_path
```

## Modes

| Mode | Behavior |
| --- | --- |
| `shadow` | Report only; no claim write for wait; no Cursor; no publication |
| `launch` | Claim + one Executor + postconditions + optional publication |

## First pilot failure (regression)

Required report + unexpected `uv.lock` + exit 0 → Coordinator must **not** commit/push.

## Hosted CI

Still a final merge-candidate gate only. Coordinator never creates PRs or dispatches Actions.
