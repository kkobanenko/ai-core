# Persistent Coordinator Runner

Status: **implemented (activation pending operator review)**

Date: 2026-09-12

## Purpose

After one-time operator activation, the persistent runner removes the per-package
terminal command. The runner polls allowlisted local git clones, discovers only
`coord/bridge/*` remote branches, prepares managed worktrees, and delegates
execution/publication to the existing one-shot Coordinator (`tools.dev_coordinator.cli.run_once`).

Spec Kit artifacts (`specs/001-persistent-coordinator-runner/*`) are authoritative
for this feature. `docs/agent-bridge/next-prompt.md` remains execution transport only.

## Architecture

```text
Architect / Spec Kit
  ├─ creates target remote branch at exact base SHA
  └─ creates coord/bridge/<package> with EXECUTOR_READY prompt
                         ↓
              Persistent runner (poll)
                         ↓
       fetch + strict candidate filtering
                         ↓
     managed bridge/executor worktree prep
                         ↓
         existing dev_coordinator.run_once
                         ↓
      Cursor Executor → postconditions →
      transient cleanup → exact commit/push →
      remote verification
                         ↓
           local terminal runner state (XDG)
                         ↓
               Architect review
```

## Safety boundaries

- Discovery namespace is exactly `coord/bridge/*` (historical `test/*` branches ignored).
- `target_repo` must be in the runner config allowlist.
- `target_worktree` must resolve under `managed_worktree_root`.
- Target branches `main` and `master` are rejected.
- No force/reset/clean shortcuts; worktree reuse only on exact repo/branch/SHA/clean match.
- No automatic claim reclaim; Coordinator claims remain exactly-once authoritative.
- No hosted CI, PR merge, tag, release, or deploy from the runner.
- No modification of `src/ai_core/**`, provider/runtime/tracing, or consumer repos.

## Configuration

Default path: `~/.config/ai-core-dev-coordinator/runner.json`

```json
{
  "poll_interval_seconds": 15,
  "coordinator_repo_root": "/absolute/path/to/coordinator-checkout",
  "managed_worktree_root": "/absolute/path/to/.coordinator-worktrees",
  "agent_bin": "/absolute/path/to/agent",
  "bridge_prefix": "coord/bridge/",
  "repositories": {
    "kkobanenko/ai-core": "/absolute/path/to/ai-core-clone",
    "kkobanenko/platform-control": "/absolute/path/to/platform-control-clone"
  }
}
```

Parser rejects unknown keys, relative paths, duplicate clone paths, invalid poll
intervals, and any `bridge_prefix` other than `coord/bridge/`.

## Managed worktree layout

| Role | Path pattern |
| --- | --- |
| Executor | `{managed_root}/{repo-short}/{branch-sanitized}` |
| Bridge | `{managed_root}/bridge/{repo-short}/{branch-sanitized}` |

Example executor path:

`/home/operator/projects/.coordinator-worktrees/ai-core/feat-001-example`

## Runner state

Terminal results are stored atomically at:

`${XDG_STATE_HOME:-~/.local/state}/ai-core-dev-coordinator/runner-state.json`

Key: `(bridge_repo, bridge_branch, bridge_sha)`. Unchanged terminal SHA is not
relaunched after polling or service restart. A new bridge SHA may be reconsidered;
Coordinator claim semantics still apply.

Terminal runner statuses: `SUCCESS`, `FAIL_CLOSED`, `HUMAN_REQUIRED`,
`EXECUTOR_FAILED`, `PUBLICATION_FAILED`, `REJECTED`.

## Commands

### One-time install (operator, after Architect review)

```bash
python3.10 scripts/install_dev_coordinator_runner.py \
  --coordinator-repo /path/to/coordinator-checkout \
  --managed-worktree-root /path/to/.coordinator-worktrees \
  --repo kkobanenko/ai-core=/path/to/ai-core \
  --repo kkobanenko/platform-control=/path/to/platform-control \
  --agent-bin "$(command -v agent)" \
  --enable
```

Without `--enable`, the installer writes config and unit files only.

### Status (read-only)

```bash
PYTHONPATH=/path/to/coordinator-checkout \
python3.10 -m tools.dev_coordinator.runner \
  --config ~/.config/ai-core-dev-coordinator/runner.json \
  --status
```

### Single scan (smoke test)

```bash
PYTHONPATH=. python3.10 -m tools.dev_coordinator.runner \
  --config /path/to/runner.json \
  --once
```

### Service observability

```bash
systemctl --user status ai-core-dev-coordinator-runner.service --no-pager
journalctl --user -u ai-core-dev-coordinator-runner.service -n 100 --no-pager
```

## Activation and rollback

**Activation** is a deliberate operator action after merge/review (`--enable`).
Implementation tests never start the live service.

**Rollback before activation**: disable feature branch; no service exists.

**Rollback after activation**:

```bash
systemctl --user disable --now ai-core-dev-coordinator-runner.service
```

Manual one-shot Coordinator remains available throughout.

## Normal future workflow

1. User writes `Твой ход` in ChatGPT.
2. Architect publishes Spec Kit package + remote target/bridge branches.
3. Runner detects `coord/bridge/*`, prepares worktrees, invokes Coordinator once.
4. Coordinator launches Cursor, validates, commits/pushes exact paths, verifies remote.
5. User writes `Твой ход` again; Architect reviews GitHub.

No per-package terminal command is required after activation.
