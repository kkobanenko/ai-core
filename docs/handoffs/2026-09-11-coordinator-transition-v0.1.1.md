# Handoff: Coordinator transition v0.1.1 LIVE-PILOT-READY

Date: 2026-09-11
Worktree: `/home/kok4444/projects/ai-core-coordinator-transition`
Primary checkout (untouched): `/home/kok4444/projects/ai-core` on `main`

## Branch / SHAs

| Item | Value |
| --- | --- |
| branch | `chore/coordinator-transition-v0.1-20260911` |
| old head (pre v0.1.1) | `d2cbca372d2f3d8673127fd0350be3aa2b82e18b` |
| new head | prefer `git rev-parse origin/chore/coordinator-transition-v0.1-20260911` after push |
| base / origin/main | `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e` |
| active bridge branch | `test/ai-core-compatibility-characterization-20260909` |
| active bridge head | `36a8a1e4334b713ffb196f6464229b47d8c50592` |

## Files changed (v0.1.1 hardening)

- `tools/dev_coordinator/claim.py` — exactly-once persistent claim
- `tools/dev_coordinator/locks.py` — `fcntl.flock` process singleton
- `tools/dev_coordinator/paths.py` — XDG state dir layout
- `tools/dev_coordinator/gitutil.py` — origin canonicalize + ls-remote helpers
- `tools/dev_coordinator/parse.py` — duplicate-key fail closed; EXECUTOR_READY required fields
- `tools/dev_coordinator/safety.py` — target_repo + bridge source + freshness
- `tools/dev_coordinator/decision.py` — launch+allow-dirty forbidden
- `tools/dev_coordinator/cli.py` — `--bridge-worktree`, claim/lock wiring, governance from executor_worktree
- `tools/dev_coordinator/executor.py` — governance labeling
- `tools/dev_coordinator/__init__.py` — version `0.1.1`
- `tests/test_dev_coordinator.py` — expanded unit + fake-agent integration
- `docs/coordination/COORDINATOR_RUNBOOK.md`
- `docs/coordination/ARCHITECT_EXECUTOR_PROTOCOL.md`
- this handoff

## Claim design

Identity string:

```text
prompt_id|target_repo|target_branch|base_sha|sha256(raw next-prompt.md)
```

File: `$STATE/claims/<sha256(identity)>.json` via `O_CREAT|O_EXCL`.
Existing claim → no second launch. No timeout reclaim.

## Lock design

`$STATE/locks/coordinator.lock` with exclusive non-blocking `fcntl.flock`.
Default state root: `${XDG_STATE_HOME:-~/.local/state}/ai-core-dev-coordinator/`
Override: `AI_CORE_COORDINATOR_STATE_DIR` or `--state-dir`.

## Bridge verification design

`--bridge-worktree` required for launch. Prompt must live inside it. Git worktree +
branch + HEAD required. Launch requires `git ls-remote` tip == local HEAD.

## Target repository validation

Canonicalize `origin` URL to `OWNER/REPO` and compare to metadata `target_repo`.

## Governance source

Loaded from **executor_worktree** `AGENTS.md` + `.cursor/rules/**` only.

## Tests added / results

Covered: legacy WAIT, metadata WAIT, EXECUTOR_READY launch decision, no-launch
states, unknown/multi state, duplicate keys, missing EXECUTOR_READY fields,
shadow zero mutation, max_executor_runs, dirty, launch+allow-dirty ban, base SHA
mismatch, target_repo mismatch, URL canonicalize, claim exactly-once, flock
singleton, governance from executor tree, bridge path enclosure, fake-agent
integration (launch once + second blocked), concurrent Coordinators (at most one
launch).

Local commands:

```bash
PYTHONPATH=.:src python3.10 -m pytest -q
PYTHONPATH=.:src python3.10 -m pytest -q tests/test_dev_coordinator.py
python3.10 -m compileall -q src tools
git diff --check
```

Results: **104 passed** (coordinator suite 33 passed); compileall OK; `git diff --check` OK.

Shadow WAIT against active bridge: `state=WAIT`, `action=NONE`, `would_launch=false`, `executor_launched=false`.

## Confirmations

- Real Cursor **NOT** launched in this task (fake-agent / mocks only)
- S2A **NOT** started
- Active bridge untouched
- Primary checkout untouched
- PR #3/#4/#5 untouched
- **NO PR** created
- **NO HOSTED CI** requested (feature-branch push only; workflow still `main`/`pull_request→main`)

## Known limitations

- Manual claim cleanup after crash (no auto-reclaim)
- No daemon / polling / Architect automation
- Executor still owns commit/push/report
- Bridge remote check needs network for `ls-remote` on launch
- `gh` auth may be broken in environment; git SSH used for push

## Rollback

```bash
git push origin --delete chore/coordinator-transition-v0.1-20260911   # Architect-authorized only
# or reset feature branch to d2cbca3
rm -rf "${XDG_STATE_HOME:-$HOME/.local/state}/ai-core-dev-coordinator"  # drops claims/locks only
```

## Live pilot readiness

**Is Coordinator now safe for ONE controlled live Executor pilot?**

### YES

(With Architect-prepared `EXECUTOR_READY` metadata, clean declared worktree,
correct `--bridge-worktree`, and acceptance that a crash leaves a blocking claim.)

Exact future command (DO NOT run in this task):

```bash
cd /home/kok4444/projects/ai-core-coordinator-transition
PYTHONPATH=. python3.10 -m tools.dev_coordinator --mode launch --once --json \
  --bridge-worktree <ACTIVE_BRIDGE_WORKTREE> \
  --bridge-prompt <ACTIVE_BRIDGE_WORKTREE>/docs/agent-bridge/next-prompt.md \
  --executor-worktree <DECLARED_TARGET_WORKTREE_MATCHING_METADATA> \
  --repo-root /home/kok4444/projects/ai-core-coordinator-transition \
  --agent-bin agent
```

---

```text
STATUS: ARCHITECT_REVIEW_REQUIRED
LIVE CURSOR NOT STARTED
S2A NOT STARTED
NO PR CREATED
NO HOSTED CI REQUESTED
```
