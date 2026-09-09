# AI Core Governance Decision Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce six OPEN governance decision packets and a documentation-only PR #3-#5 decomposition plan backed by refreshed read-only evidence.

**Architecture:** One authoritative decision document owns recommendations and evidence. One separate decomposition document maps each existing PR block to a future disposition without touching PR branches. Agent bridge points to those artifacts and ends in WAIT state.

**Tech Stack:** Markdown, Git read-only inspection, GitHub CLI read-only queries, existing Python 3.10 verification scripts

## Global Constraints

- Work only on `test/ai-core-compatibility-characterization-20260909`.
- Change only coordination/documentation artifacts; never `src/ai_core/**`, consumers, platform-control, PR branches, PR metadata, tags, releases, or deployment.
- Keep every governance decision `OPEN`; recommendations are decision support only.
- Do not accept new provider identities, capabilities, or `STT_SEGMENTS`.
- Do not create, modify, merge, rebase, rewrite, or split PR #3-#5.
- Distinguish observed fact, inference, and recommendation.
- Preserve user-owned `.worktrees/`, `docs/tmp/`, and `uv.lock`.

---

### Task 1: Refresh evidence ledger

**Files:**
- Read: `docs/reports/2026-09-09-ai-core-compatibility-characterization-report.md`
- Read: `docs/architecture/cross_project_ai_inventory.md`
- Read: `docs/architecture/source_of_truth_map.md`
- Read: `/home/kok4444/projects/platform-control/config/compatibility.yaml`
- Read: `/home/kok4444/projects/platform-control/coordination/current-initiative.yaml`
- Create through Task 2: `docs/governance/2026-09-09-ai-core-decision-packets.md`

**Interfaces:**
- Consumes: immutable SHAs, existing characterization, GitHub PR/issue state, pinned consumer evidence
- Produces: dated evidence ledger used by every decision packet and decomposition row

- [ ] **Step 1: Capture repository and remote facts**

Run read-only commands:

```bash
git rev-parse HEAD
git rev-parse main
git ls-remote origin refs/heads/main refs/heads/test/ai-core-compatibility-characterization-20260909
git status --short --branch
```

Record exact SHAs and preserve any user-owned untracked paths.

- [ ] **Step 2: Capture PR #3-#5 state and file-level diffs**

Run for each PR:

```bash
gh pr view NUMBER --json number,title,state,isDraft,headRefName,headRefOid,baseRefName,mergeable,reviewDecision,statusCheckRollup,updatedAt,url,body
gh api repos/kkobanenko/ai-core/pulls/NUMBER/files --paginate
```

Record actual head/base, review state, CI, logical blocks, and changed symbols.
Do not edit PR metadata.

- [ ] **Step 3: Capture platform-control authority state**

Read current tracked files and query issues #291-#293, including comments. Record
whether any explicit approval exists. Compare recorded `ai_core_main_sha` with
factual `origin/main`; retain observed-state drift unless values now match.

- [ ] **Step 4: Reconcile consumer and capability evidence**

Recheck pinned consumer fixtures and report evidence. Label Mistral OCR live
success as runtime-observed for that exact path, Ollama endpoint normalization
and reachability as reachability evidence, and GPU vision HTTP 503 as
failed/inconclusive runtime validation. Never infer GPU runtime capability.

### Task 2: Write six OPEN decision packets

**Files:**
- Create: `docs/governance/2026-09-09-ai-core-decision-packets.md`

**Interfaces:**
- Consumes: Task 1 evidence ledger
- Produces: decision IDs D1-D6, with D6a and D6b independently approvable

- [ ] **Step 1: Add status and evidence legend**

Document `OPEN`, decision authority, evidence timestamp, fact/inference/
recommendation labels, and evidence levels `CONFIGURED`, `UNIT_TESTED`,
`INTEGRATION_TESTED`, `RUNTIME_OBSERVED`, `FAILED_INCONCLUSIVE`.

- [ ] **Step 2: Write D1-D3**

For baseline/foundation, privacy/egress, and provider identity/capability scope,
use exact fields:

```text
Question
Why it matters
Current evidence
Recommended decision
Alternatives
Consequences of recommended choice
Consequences of alternatives
What remains deferred
Effect on PR #3 / #4 / #5
What this unlocks
Required authority
Status: OPEN
```

Recommend additive submodules with unchanged root API; all-form `SECRET` denial
before routing; missing egress authorization fails closed; accepted four-ID set
stays fixed pending separate approval.

- [ ] **Step 3: Write D4-D5**

Keep provider-call retry, provider fallback, and durable job/workflow retry as
three distinct contracts. Recommend future AI Core execution-layer ownership of
provider-call retry and provider fallback orchestration, while durable retry
remains consumer-owned. Cover route order, deterministic tie-break, `UNKNOWN`
health, canonical errors, and shared end-to-end deadline without implementing
an executor.

- [ ] **Step 4: Write D6a-D6b within D6**

Make GPU trust/network boundary independent from HTTP service ownership/auth/
deployment. State that neither subdecision accepts STT, new identities, or the
other subdecision. Preserve exact GPU evidence language from Task 1.

- [ ] **Step 5: Add operator choice sheet**

End with compact list of explicit choices and recommended selections. Every box
remains unchecked and every status remains `OPEN`.

### Task 3: Write PR #3-#5 paper decomposition

**Files:**
- Create: `docs/governance/2026-09-09-ai-core-pr-decomposition-plan.md`

**Interfaces:**
- Consumes: decision IDs D1-D6 and pinned PR diffs
- Produces: future mechanical split sequence; performs no Git or GitHub mutation

- [ ] **Step 1: Define disposition vocabulary**

Use only `FOUNDATION_CANDIDATE`, `FIX_BEFORE_FOUNDATION`,
`SEPARATE_GOVERNED_WP`, `DEFER_TO_RUNTIME`, and `REJECT_REDESIGN`. Define that
labels are recommendations, not merge authorization.

- [ ] **Step 2: Decompose PR #3**

Map exact files/symbols into root compatibility, dependency-light catalog,
capability policy, privacy behavior, and docs/tests. Mark transformed `SECRET`
egress `REJECT_REDESIGN`; gate remaining foundation pieces on D1-D3.

- [ ] **Step 3: Decompose PR #4**

Separate alias/evidence machinery for accepted IDs from `gpu_whisper`,
`openai_external`, `deepseek_external`, and `STT_SEGMENTS`. Keep proposed
identities/capability in separate governed work; do not silently accept them.

- [ ] **Step 4: Decompose PR #5**

Separate pure deadline arithmetic from routing/health/errors and from future
execution. Mark implicit egress and inherited transformed `SECRET` behavior
`REJECT_REDESIGN`; mark transports/executor `DEFER_TO_RUNTIME`.

- [ ] **Step 5: Add future sequencing and validation gates**

For each future slice record prerequisite decision IDs, intended base, retained
blocks, exclusions, tests, rollback, and stop condition. Describe branch work as
future operator-authorized action only.

### Task 4: Validate and publish handoff

**Files:**
- Modify: `docs/agent-bridge/latest-report.md`
- Create: `docs/agent-bridge/reports/2026-09-09-ai-core-governance-decision-support.md`
- Modify: `docs/agent-bridge/next-prompt.md`

**Interfaces:**
- Consumes: Tasks 1-3 artifacts and validation output
- Produces: durable review handoff ending in WAIT

- [ ] **Step 1: Validate content state**

Run:

```bash
env PYTHONPATH=src python3.10 -m pytest -q
python3.10 scripts/verify_consumer_contract_fixtures.py --workspace-root /home/kok4444/projects
python3.10 scripts/check_characterization_changed_paths.py --base 7569441c18362cfd15524ad73f56f7f35580c86f --head HEAD
git diff --check 7569441c18362cfd15524ad73f56f7f35580c86f...HEAD
```

Record exact results. Existing warning may be documented; failure must be
investigated without production changes.

- [ ] **Step 2: Audit scope and placeholders**

Confirm changed paths are documentation/coordination only. Scan authoritative
artifacts for standard unfinished-marker tokens, accidental accepted status,
credentials, and contradictory recommendations.

- [ ] **Step 3: Update bridge**

Make `latest-report.md` point to authoritative decision and decomposition docs.
Archive concise results, SHAs, checks, risks, blockers, rollback, and next WP.
Replace `next-prompt.md` with WAIT instruction forbidding runtime, PR mutation,
merge, release, and deployment until explicit new scope and decisions exist.

- [ ] **Step 4: Commit and push documentation artifacts**

Commit only listed documentation paths. Push only current branch. Verify remote
HEAD equals local HEAD and main remains unchanged. Do not create or update any
pull request because current user scope does not authorize PR creation.
