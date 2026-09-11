# AI Core S1 Foundation Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved dependency-light S1 identity, capability/evidence, and privacy/egress contracts without changing root compatibility.

**Architecture:** Three standard-library-only explicit submodules separate identity metadata, evidence semantics, and pre-routing egress decisions. Tests are written first for each module. Package root and tracing stay isolated.

**Tech Stack:** Python 3.10+, dataclasses, enum, types.MappingProxyType, pytest.

## Global Constraints

- Base is `ai-core/main@7569441c18362cfd15524ad73f56f7f35580c86f`.
- Authoritative governance is `platform-control/main@c78b5e735d9b47e6550f2f6f7df084406c3ecfe0`.
- Root `ai_core.__all__` remains the exact existing nine symbols.
- Only the four accepted provider IDs are represented.
- No runtime, network, service, transport, executor, retry/fallback execution, consumer, alias, route, health, deadline, STT, deployment, release, or tag implementation.
- No dependency or lock-file changes.
- PR #3-#5 remain immutable evidence.

---

### Task 1: Provider identity contracts

**Files:**
- Create: `tests/test_s1_provider_catalog.py`
- Create: `src/ai_core/provider_catalog.py`

**Interfaces:**
- Produces: `NetworkBoundary`, `ProviderIdentity`, `UnknownProviderIdentityError`, four provider constants, `CANONICAL_PROVIDER_IDS`, `get_provider_catalog()`, and `get_provider_identity(provider_id)`.

- [ ] **Step 1: Write failing provider tests**

Test the exact four-ID tuple, boundary mapping, immutable/minimal dataclass
fields, read-only catalog, and explicit error for an unknown ID.

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src python3.10 -m pytest -q tests/test_s1_provider_catalog.py`

Expected: collection failure because `ai_core.provider_catalog` does not exist.

- [ ] **Step 3: Implement minimal identity module**

Use only `dataclasses`, `enum`, `types`, and `typing`. Define no operational or
behavioral provider metadata.

- [ ] **Step 4: Verify GREEN**

Run the focused test and then the full local suite.

### Task 2: Capability evidence contracts

**Files:**
- Create: `tests/test_s1_capability_evidence.py`
- Create: `src/ai_core/capabilities.py`

**Interfaces:**
- Consumes: provider identity lookup and `NetworkBoundary`.
- Produces: `ProviderCapability`, `CapabilityEvidenceLevel`,
  `CapabilityEvidence`, and `has_runtime_observation(evidence)`.

- [ ] **Step 1: Write failing evidence tests**

Test exact evidence levels, absence of STT, full evidence subject, unknown-ID
and boundary-mismatch rejection, and non-promotion of every level except an
actual runtime observation.

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src python3.10 -m pytest -q tests/test_s1_capability_evidence.py`

Expected: collection failure because `ai_core.capabilities` does not exist.

- [ ] **Step 3: Implement minimal evidence module**

Add pure enum/dataclass validation only. Add no model registry, route, health,
or provider execution behavior.

- [ ] **Step 4: Verify GREEN**

Run the focused tests and all implemented S1 tests.

### Task 3: Privacy and egress contracts

**Files:**
- Create: `tests/test_s1_privacy_egress.py`
- Create: `src/ai_core/privacy.py`

**Interfaces:**
- Consumes: `NetworkBoundary`.
- Produces: `DataClass`, `OutboundForm`, and keyword-only
  `is_egress_eligible(data_class, outbound_form, network_boundary, request_egress_authorized=False)`.

- [ ] **Step 1: Write failing privacy tests**

Parameterize all nine SECRET combinations; test transformed SECRET remains
denied; test missing external/unknown authorization fails closed; and test
non-secret local and explicitly authorized egress.

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=src python3.10 -m pytest -q tests/test_s1_privacy_egress.py`

Expected: collection failure because `ai_core.privacy` does not exist.

- [ ] **Step 3: Implement minimal pre-routing decision**

Apply SECRET denial first, then require request authorization for `EXTERNAL`
and `UNKNOWN_BOUNDARY`. Add no provider profile or fallback executor inputs.

- [ ] **Step 4: Verify GREEN**

Run focused privacy tests and all S1 tests.

### Task 4: Compatibility and scope proof

**Files:**
- Create: `tests/test_s1_compatibility_boundary.py`

**Interfaces:**
- Consumes: existing package root and all S1 modules.
- Produces: reviewable proof that S1 is additive and dependency-light.

- [ ] **Step 1: Write compatibility tests**

Test exact root `__all__`, subprocess import isolation, unchanged project
dependency list, and absence of alias/STT/new-ID symbols from S1 surfaces.

- [ ] **Step 2: Run full verification**

Run Python 3.10 full pytest, `git diff --check`, and changed-path/dependency
audits. Run Python 3.12 if available; otherwise rely on hosted matrix.

- [ ] **Step 3: Run read-only characterization/consumer evidence**

Use the existing characterization branch and its pinned fixtures without
changing their expectations. Record any unavailable external environment as a
limitation rather than weakening tests.

### Task 5: Review surface and handoff

**Files:**
- Create: `docs/handoffs/2026-09-11-ai-core-s1-foundation-contracts.md`
- Update only bridge documentation on the existing bridge branch after PR publication.

- [ ] **Step 1: Document provenance and exact exclusions**

Record which PR #3 ideas were reimplemented, redesigned, or excluded, plus
base/head, tests, risks, rollback, and the authoritative governance SHA.

- [ ] **Step 2: Commit and push S1 branch**

Use conventional commits and preserve the isolated worktree.

- [ ] **Step 3: Create draft AI Core PR**

Target `main`, state all scope boundaries, and do not merge.

- [ ] **Step 4: Verify hosted exact-head CI**

Fix only failures inside approved S1 scope.

- [ ] **Step 5: Update bridge and stop**

Archive the report, set next prompt to WAIT, push bridge docs, and return to
operator review. Future S1 merge requires separate explicit authorization.
