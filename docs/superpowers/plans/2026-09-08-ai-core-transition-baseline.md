# AI Core Transition Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an evidence-backed compatibility and governance baseline for the AI Core consolidation without changing any runtime or consumer.

**Architecture:** Collect immutable and current repository evidence first, then normalize it into three canonical documents. Keep observed facts, governance decisions, proposals, and unknowns distinct; close with a handoff that makes the next bounded decision explicit.

**Tech Stack:** Git/GitHub CLI, ripgrep, Python/pytest, Markdown, YAML governance records.

## Global Constraints

- Do not change `main`, immutable tags, releases, consumers, infrastructure, provider identities, capabilities, or any runtime behavior.
- Preserve user-owned untracked `.worktrees/` and `uv.lock` in the main checkout.
- Prozakupki, KMO, Alpha, and every other consumer are read-only evidence sources.
- Do not accept `STT_SEGMENTS`, resolve `pending_decision`, merge PRs #3-#5, or infer governance approval from green CI.
- Record unknowns and blockers explicitly and continue other safe workstreams.

---

### Task 1: Capture Repository and Governance Baseline

**Files:**
- Create: `docs/migration/current_state_baseline.md`

**Interfaces:**
- Consumes: git refs/tags, GitHub PR metadata, platform-control allowlist/compatibility/initiative/review records.
- Produces: authoritative evidence snapshot used by Tasks 2-5.

- [ ] **Step 1: Record the exact ai-core repository state**

Run `git status --short --branch`, `git branch -vv`, `git log --oneline --decorate --graph --all -80`, and peeled tag resolution with `git rev-list -n 1 <tag>`.

- [ ] **Step 2: Record PR #3, #4, and #5 state**

Run `gh pr view` for each PR and capture base/head SHA, draft state, CI, declared governance review, scope, and rollback.

- [ ] **Step 3: Resolve the platform-control review state**

Inspect review PRs #291-#293 plus the current compatibility and initiative records. Classify each decision as accepted, rejected, pending, stale/local-only, or absent; never infer acceptance.

- [ ] **Step 4: Write the baseline document**

Include production baseline, immutable releases, divergent historical lines, relevant branches, open PRs, tests, known consumers/providers, governance blockers, and a timestamped evidence note.

### Task 2: Build the Cross-Project AI Inventory

**Files:**
- Create: `docs/architecture/cross_project_ai_inventory.md`

**Interfaces:**
- Consumes: Task 1 baseline plus read-only project manifests, source, configs, tests, and documentation.
- Produces: project-by-project current AI paths and exact evidence locations.

- [ ] **Step 1: Enumerate projects without relying on the historical allowlist**

Inspect every top-level directory under `/home/kok4444/projects`, detect repositories, and reconcile them with `platform-control/config/projects.yaml` and current initiative registries.

- [ ] **Step 2: Search all candidate projects for AI evidence**

Use the transition-plan term set plus dependency pins, direct HTTP endpoints, SDKs, retry/fallback, privacy, tracing, OCR, vision, and STT patterns. Exclude `.git`, generated caches, vendored dependencies, and build outputs from primary evidence.

- [ ] **Step 3: Validate material findings in source context**

Read manifests, provider configs, adapters, clients, and tests for every positive match. Record commit/branch/dirty state so evidence is not presented as production when it is only WIP.

- [ ] **Step 4: Write the normalized inventory**

For every allowlisted project state `uses AI` or `does not use AI`. Add discovered non-allowlisted consumers separately and populate current path, pin, providers/models, registry, direct clients, retry, fallback, privacy, media capabilities, tracing, migration risk, and exact paths.

### Task 3: Define the Source-of-Truth Map

**Files:**
- Create: `docs/architecture/source_of_truth_map.md`

**Interfaces:**
- Consumes: Tasks 1-2 and accepted platform-control ADRs/matrix entries.
- Produces: concern ownership boundaries for future implementation planning.

- [ ] **Step 1: Separate observed, temporary, future, and product ownership**

Cover tracing, provider/model registry, capabilities, credentials, privacy/egress, routing, health, retry/fallback, deadlines, structured errors/output, transports, prompts, schemas, queues, persistence, authorization, and observability deployment.

- [ ] **Step 2: Mark governance-qualified ownership**

State where the desired future owner is proposed by the transition plan but conflicts with or extends the currently accepted ADR/matrix. Keep proposed identities and `STT_SEGMENTS` pending.

- [ ] **Step 3: Record extraction rules and migration invariants**

Document `extract -> compare -> generalize -> contract -> implement`, single fallback ownership, fail-closed privacy, compatibility adapters, consumer rollback, and the prohibition on copying product prompts/schemas/workflow state.

### Task 4: Audit Compatibility and Test Coverage

**Files:**
- Modify: `docs/migration/current_state_baseline.md`
- Modify: `docs/architecture/cross_project_ai_inventory.md`

**Interfaces:**
- Consumes: current tests, immutable tag trees, historical branches, and consumer contracts.
- Produces: current coverage matrix and prioritized missing tests; no runtime/test implementation in this work package.

- [ ] **Step 1: Audit main root/tracing coverage**

Run `PYTHONPATH=src python3.10 -m pytest -q`, inspect `tests/test_v01_public_api_contract.py`, and compare public signatures/defaults against `v0.1.0` and main.

- [ ] **Step 2: Audit historical ai-core inference contracts**

Inspect tags `v0.2.0`-`v0.2.2` and relevant provider branches for `LangChainJsonClient`, provider construction, invocation methods, capabilities, privacy, errors, dependencies, and tests.

- [ ] **Step 3: Audit consumer representability contracts**

For Prozakupki, KMO, and every other detected consumer, identify observable provider/model selection, timeout, retry/fallback, environment, structured-output, privacy, tracing, and media expectations.

- [ ] **Step 4: Record missing compatibility tests**

Prioritize gaps by breakage risk and assign each to a future bounded test work package. Do not copy consumer code, prompts, schemas, secrets, or fixtures containing production data.

### Task 5: Assess PRs and Produce Handoff

**Files:**
- Modify: `docs/migration/current_state_baseline.md`
- Create: `docs/handoffs/2026-09-08-ai-core-transition-baseline.md`

**Interfaces:**
- Consumes: all earlier tasks plus diffs/tests/handoffs for PRs #3-#5.
- Produces: conditional PR disposition and safe next work package.

- [ ] **Step 1: Compare each PR with the transition plan**

For each PR list aligned content, content potentially acceptable after governance review, required corrections, deferred content, dependency ordering, and compatibility risk.

- [ ] **Step 2: Verify documentation integrity**

Run `rg -n 'TBD|TODO|pending_decision.*resolved'` on the new documents, inspect every hit, run `git diff --check`, and verify all cited repository paths exist at the recorded checkout revision or are explicitly historical.

- [ ] **Step 3: Re-run the unchanged compatibility suite**

Run `PYTHONPATH=src python3.10 -m pytest -q`. Expected: the same 24 passing tests as the clean baseline; document any environment warning separately.

- [ ] **Step 4: Write the handoff and commit**

Record branch, base SHA, final head SHA or pre-commit candidate SHA, changed documents, checks, risks, blockers, rollback, remaining unknowns, and one recommended next bounded work package. Commit documentation only; do not push, merge, tag, release, or mutate consumers.
