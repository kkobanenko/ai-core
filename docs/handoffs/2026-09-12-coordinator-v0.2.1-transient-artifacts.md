# Handoff: Coordinator v0.2.1 transient artifacts

Date: 2026-09-12
Branch: `chore/coordinator-transition-v0.1-20260911`
Worktree: `/home/kok4444/projects/ai-core-coordinator-transition`

## SHAs

| Item | Value |
| --- | --- |
| old head | `f7e57c1d0299c1262592b1cc1a1842a22989d814` |
| new head | prefer remote tip after push |
| version | `0.2.1` |

## Motivation

Live pilot #2: required report OK, unexpected `uv.lock`, exit 0 → correct
`POSTCONDITION_FAILED`. Cursor stdout claimed only the report changed — therefore
Executor self-report is not authoritative. AI Core does not use uv as project
contract; do not allowlist or gitignore `uv.lock`. Instead: opt-in
`transient_paths` with strict baseline/cleanup.

## Changed files

- `tools/dev_coordinator/transient.py` (new)
- `tools/dev_coordinator/models.py`, `parse.py`, `cli.py`, `__init__.py`
- `tests/test_dev_coordinator.py`
- coordination docs + this handoff

## Transient contract

Declared exact relative paths; absent+untracked before; untracked regular file
after; SHA256 evidence; `Path.unlink` only; re-`git status`; then normal
postconditions. Never stage transients.

## Tests

Includes: pilot #2 with `transient_paths=uv.lock` success; without declaration
still `POSTCONDITION_FAILED`; existed-before; tracked/not-untracked; undeclared
second file; overlap allowed/required; path syntax negatives; cleanup then
surprise path.

## Confirmations

- Pilot #1 evidence untouched: YES
- Pilot #2 evidence untouched: YES
- S2A started: NO
- PR created: NO
- Hosted CI requested: NO

## Rollback

Reset feature branch to `f7e57c1`.

---

```text
STATUS: ARCHITECT_REVIEW_REQUIRED
PILOT_3 NOT STARTED
```
