# Handoff: Coordinator v0.2 deterministic publication

Date: 2026-09-12
Worktree: `/home/kok4444/projects/ai-core-coordinator-transition`
Branch: `chore/coordinator-transition-v0.1-20260911`

## SHAs

| Item | Value |
| --- | --- |
| old head | `0984897cfc87e26ff93a2f1f7fadd9016cecf10c` |
| new head | prefer `git rev-parse origin/chore/coordinator-transition-v0.1-20260911` after push |
| origin/main | `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e` |

## Changed files

- `tools/dev_coordinator/models.py` — `FinalStatus`, publication fields on `RunResult`/`BridgePrompt`
- `tools/dev_coordinator/parse.py` — flat `allowed_paths`/`required_paths`/publication_*
- `tools/dev_coordinator/publication.py` — postconditions + exact-path commit/push/verify
- `tools/dev_coordinator/executor.py` — Executor must-not commit/push; output tails
- `tools/dev_coordinator/cli.py` — post-launch pipeline + JSON result fields
- `tools/dev_coordinator/__init__.py` — version `0.2.0`
- `tests/test_dev_coordinator.py` — pilot#1 regression + publication matrix
- `docs/coordination/COORDINATOR_RUNBOOK.md`
- `docs/coordination/ARCHITECT_EXECUTOR_PROTOCOL.md`
- `docs/coordination/TRANSITION_PLAN.md`
- this handoff

## First pilot failure reproduced

Fake Executor creates required report + unexpected `uv.lock`, exit 0:

```text
executor_exit_code = 0
postconditions_ok = false
unexpected_paths includes uv.lock
commit_created = false
push_attempted = false
final_status = POSTCONDITION_FAILED
```

## Postcondition design

Authoritative `git status --porcelain` vs `allowed_paths` / `required_paths`.
No trust in Executor self-report. No auto-delete of unexpected files.

## Exact-path staging

`git add -- <paths>` only. Never `git add .` / `-A`.

## Commit/push ownership

Coordinator performs commit/push when metadata requests it and postconditions pass.
Refuse `target_branch` in `{main, master}`. No force push. No PR / Actions.

## Remote verification

`git ls-remote origin refs/heads/<target_branch>` must equal local HEAD.

## Observability

Stdout/stderr tails ≤ 32 KiB in JSON; full capped log under state `logs/`.
`elapsed_seconds` recorded. Raw Executor stdout not auto-committed.

## Tests / results

```bash
PYTHONPATH=.:src python3.10 -m pytest -q
PYTHONPATH=.:src python3.10 -m pytest -q tests/test_dev_coordinator.py
python3.10 -m compileall -q src tools
git diff --check
```

Expect coordinator suite ≥46 passed; full suite green.

**Observed:** 117 passed full suite; 46 coordinator tests; compileall OK; `git diff --check` OK.

## Confirmations

- NO hosted CI requested
- NO PR created
- Forensic pilot `/home/kok4444/projects/ai-core-coordinator-pilot-executor` **untouched**
  (report + `uv.lock` preserved; claim not deleted)
- S2A untouched / not started
- Active S2 bridge untouched
- Pilot #2 not started

## Limitations

- Flat comma-separated paths only (no nested YAML lists)
- No reclaim-by-timeout for claims
- No streaming heartbeat yet
- Optional validation commands DSL not implemented (only `git diff --check`)

## Rollback

Reset/delete feature branch tip to `0984897`. State dir claims/logs unaffected by rollback.

## Live pilot #2 readiness

**Is Coordinator ready for live pilot #2?**

### YES

(Do **not** start it in this task. Architect must authorize a new bridge prompt with
publication metadata and a fresh claim identity.)

---

```text
STATUS: ARCHITECT_REVIEW_REQUIRED
PILOT_1 PRESERVED AS FAILURE EVIDENCE
PILOT_2 NOT STARTED
S2A NOT STARTED
NO PR CREATED
NO HOSTED CI REQUESTED
```
