# Handoff: Coordinator transition v0.1

Date: 2026-09-11  
Worktree: `/home/kok4444/projects/ai-core-coordinator-transition`  
Primary checkout (untouched): `/home/kok4444/projects/ai-core` on `main` @ `7569441c18362cfd15524ad73f56f7f35580c86f`

## Branch / SHAs

| Item | Value |
| --- | --- |
| branch | `chore/coordinator-transition-v0.1-20260911` |
| base SHA | `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e` (`origin/main` at branch creation) |
| head SHA | prefer `git rev-parse origin/chore/coordinator-transition-v0.1-20260911` (content commits: `ac0f09b` coordinator, `19cacd7` Spec Kit; docs tip may advance) |
| current main (`origin/main`) | `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e` |
| active bridge branch | `test/ai-core-compatibility-characterization-20260909` |
| active bridge head | `36a8a1e4334b713ffb196f6464229b47d8c50592` |

## Existing branches observed (tips after fetch)

| Branch | Tip | Subject |
| --- | --- | --- |
| `origin/main` | `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e` | Merge pull request #6 … |
| `origin/test/ai-core-compatibility-characterization-20260909` | `36a8a1e4334b713ffb196f6464229b47d8c50592` | docs(bridge): recommend S2A alias scope |
| `origin/feat/ai-core-s1-foundation-contracts-20260911` | `f73a77706ab88c11ce01066c9b6c92406975da1f` | docs: record S1 draft publication |
| `origin/feat/ai-core-consolidation-foundation-20260907` | `4e26d67b825194e489a6a8b553c2a53dfea2a81f` | docs(ai-core): align foundation handoff… |
| `origin/feat/ai-core-provider-evidence-c2-20260907` | `1b2569a612968a3ac5099dea955cfccdcb191d52` | docs(ai-core): record C2 CI validation… |
| `origin/feat/ai-core-bounded-routing-c3-20260907` | `25c269bb93dd37bd9b1556051972f5e1e60b34ad` | docs(ai-core): add C3 bounded routing… |
| `origin/feat/provider-catalog-privacy-routing` | `679b88fa7cd6e9f64b543c405a90b2ef0dcdc575` | Merge PR #2: AIC-AU01B… |
| `origin/spike/au01b-multimodal-ocr-primitives` | `adf856e729b32edc702683e37aaab9d08f481856` | chore: prepare ai-core v0.2.2 release |
| `origin/chore/validate-ai-core-v0.1-v0.2` | `3373a00724fcf2346d309c5f67c48052ceffe7dc` | docs: record functional validation SHA… |
| `origin/docs/ai-core-transition-baseline-20260908` | `65a865e5eef38e44559d98ab9187d5d59b8fa2e7` | docs: hand off AI transition baseline |
| `origin/ai-core-task2-tracing` | `e479d0af314714a96c959a2ea677abdcb0942af7` | chore: prepare ai-core v0.2.0 |
| `origin/chore/platform-control-phase1` | `076333e68db109d11920a17f59a2adb2ac8ec3c8` | chore: document Python>=3.10… |

No rebase/merge/force-push/delete/retarget/amend/normalize of foreign branches.

## Files changed (this branch)

- `tools/__init__.py`
- `tools/dev_coordinator/**` — deterministic Coordinator v0.1
- `tests/test_dev_coordinator.py`
- `pyproject.toml` — pytest `pythonpath` for `tools.*`
- `docs/coordination/TRANSITION_PLAN.md`
- `docs/coordination/ARCHITECT_EXECUTOR_PROTOCOL.md`
- `docs/coordination/COORDINATOR_RUNBOOK.md`
- `docs/coordination/GITHUB_ACTIONS_QUOTA_POLICY.md`
- `docs/coordination/SPEC_KIT_ADOPTION.md`
- `docs/handoffs/2026-09-11-coordinator-transition-v0.1.md` (this file)
- `.specify/**` — Spec Kit v1.0.6 scaffold
- `.cursor/skills/speckit-*/**` — Spec Kit Cursor skills (coexist with rules)

## Files intentionally untouched

- Active `docs/agent-bridge/**` on bridge branch (including `next-prompt.md` WAIT)
- `AGENTS.md`
- `.cursor/rules/**`
- `src/ai_core/**`
- `.github/workflows/**`
- PR #3, #4, #5 and their branches
- platform-control (read-only inspection only)
- Primary worktree branch/checkout

## Spec Kit

- Installed: **specify-cli / Spec Kit v1.0.6** (`96c9bd657bfd5de0d651a6165084932b7304ac99`)
- Init: `specify init --here --force --non-interactive --integration cursor-agent --ignore-agent-tools`
- Governance overwrite check: **PASS** (`AGENTS.md` / `.cursor/rules` unchanged)
- Constitution: upstream placeholder only; not adopted for in-flight S2/S2A

## Coordinator modes

- `--mode shadow` (default): report-only, zero mutations
- `--mode launch`: at most one Cursor launch when `EXECUTOR_READY` + safety
- `--once`: single evaluation and exit

Verified CLI launch shape: `agent --print --workspace <path> --trust <prompt>`  
(`agent` version observed: `2026.08.04-aaa8809`)

## Local tests (exact)

```bash
PYTHONPATH=.:src python3.10 -m pytest -q
PYTHONPATH=.:src python3.10 -m pytest -q tests/test_dev_coordinator.py
python3.10 -m compileall -q src tools
git diff --check
```

Shadow against live legacy WAIT (read-only path to active bridge file):

```bash
PYTHONPATH=.:src python3.10 -m tools.dev_coordinator --mode shadow --once --json \
  --bridge-prompt <bridge-worktree>/docs/agent-bridge/next-prompt.md \
  --repo-root <this-worktree> --executor-worktree <this-worktree>
```

Result: `action=NONE`, `state=WAIT`, `would_launch=false`, `mutations=[]`.

## Test results

- Full suite: **90 passed**
- Coordinator unit tests: **19 passed**
- `compileall`: OK
- `git diff --check`: OK
- Hosted CI: **not invoked**

## Confirmations

- **No hosted CI was triggered intentionally** (workflow still `push/PR → main` only; this is a feature branch push only).
- **No PR was created.**
- **PR #3 / #4 / #5 were untouched.**
- **Active agent-bridge was untouched** (still WAIT / S2 DISCOVERY COMPLETE — RECOMMEND S2A ONLY).
- **S2A was not started.**

## Known limitations (v0.1)

- Does not own commit/push/report publication (Executor retains legacy ownership).
- No autonomous loop; human must re-invoke / say «Твой ход».
- Simple flat YAML front matter only (no nested structures).
- Executor lock detection is a parameter hook (`executor_lock_held`), not a full filesystem lock service yet.
- `docs/agent-bridge` is absent on `main`-based tree; Coordinator reads an explicit `--bridge-prompt` path until bridge lands on the working tree.
- `gh auth` was invalid in this environment at task time; git SSH push used for the feature branch.

## Risks

- Future Spec Kit skills could tempt mid-flight S2 conversion — policy forbids that.
- Accidental PR to `main` would consume Actions quota.
- Launch mode with wrong `--executor-worktree` could target an unintended tree — mitigated by declared metadata + fail-closed checks.
- Local primary `main` checkout remains behind `origin/main` (`7569441` vs `f65221b`); operators must not “fix” it via this branch.

## Rollback

```bash
# Drop remote feature branch if needed (Architect-authorized only)
git push origin --delete chore/coordinator-transition-v0.1-20260911

# Remove local worktree
git -C /home/kok4444/projects/ai-core worktree remove \
  /home/kok4444/projects/ai-core-coordinator-transition
```

No runtime/production state was changed. Active bridge and PRs remain as before.

## Recommended next step

1. Architect reviews this branch + docs (shadow-only practice against WAIT).
2. Finish in-flight S2/S2A under **old** agent-bridge scheme when authorized.
3. For the first **new** package after S2A closeout, authorize Spec Kit–native planning while keeping bridge as control channel.
4. Optionally design v0.2 ownership move for commit/push/report publication.

---

```text
STATUS: ARCHITECT_REVIEW_REQUIRED
NO PR CREATED
NO HOSTED CI REQUESTED
```
