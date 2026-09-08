# AI Core Compatibility Characterization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an executable, provenance-backed compatibility safety net for current ai-core, immutable historical releases, consumer infrastructure requirements, privacy invariants, and draft PR #3–#5 evidence without changing production behavior.

**Architecture:** Keep all implementation under `tests/`, `scripts/`, `.github/`, and `docs/`. Portable tests consume synthetic fixtures; Git-ref tests inspect exact immutable objects without imports; isolated loaders exercise only selected historical behavior with fakes; a workspace verifier checks recorded consumer facts through exact Git objects rather than working trees.

**Tech Stack:** Python 3.10 standard library, pytest, Git object plumbing, JSON fixtures, subprocess isolation, Markdown.

## Global Constraints

- Base production SHA remains `7569441c18362cfd15524ad73f56f7f35580c86f`; this branch starts from documentation handoff `65a865e5eef38e44559d98ab9187d5d59b8fa2e7`.
- Never modify `src/ai_core/**`, `pyproject.toml`, a consumer, platform-control, runtime/service/config production code, a release, or a tag.
- Do not accept a new provider identity or `STT_SEGMENTS`; the accepted provider IDs remain exactly `vm100_local_ollama`, `gpu_ollama`, `ollama_cloud`, and `mistral_external`.
- Historical behavior is `OBSERVED_HISTORICAL_EVIDENCE`, versioned separately for v0.1.0, v0.2.0, v0.2.1, and v0.2.2.
- `SECRET` means inference denied, no eligible route, and zero provider attempts for every outbound form and boundary.
- Consumer fixtures separate observed evidence, consumer requirement, accepted platform contract, proposed behavior, and governance-pending behavior.
- Provider-call retry, provider fallback, and durable job retry are distinct fields.
- Tests perform no network fetch/provider call and receive no real credentials.
- Preserve user-owned `.worktrees/` content and `uv.lock`; do not push, merge, release, tag, or change `main`.

---

### Task 1: Current v0.1 contract and dependency boundary

**Files:**
- Create: `tests/compatibility/__init__.py`
- Create: `tests/compatibility/test_current_v01_contract.py`
- Create: `tests/compatibility/test_dependency_boundary.py`

**Interfaces:**
- Consumes: current `ai_core` root and tracing modules.
- Produces: exact signature expectations and `run_isolated_import_probe() -> dict[str, object]` test helper local to the dependency test.

- [ ] **Step 1: Extend the existing v0.1 contract with signature tests**

Add assertions without duplicating `tests/test_v01_public_api_contract.py`:

```python
EXPECTED_SIGNATURES = {
    "init_tracing": "(project_name: 'str | None' = None) -> 'object | None'",
    "load_phoenix_config": "() -> 'PhoenixConfig'",
    "maybe_truncate": "(text: 'str | None', max_chars: 'int') -> 'str | None'",
    "record_llm_result": "(span: 'object | None', *, response_text: 'str' = '', status: 'str', latency_ms: 'int | None' = None, fallback_mode: 'str | None' = None, error_type: 'str | None' = None) -> 'None'",
    "sanitize_attributes": "(attributes: 'Mapping[str, object] | None') -> 'dict[str, AttributeValue]'",
    "shutdown_tracing": "() -> 'None'",
    "start_llm_span": "(*, workflow: 'str', attributes: 'Mapping[str, AttributeValue] | None' = None, system_prompt: 'str' = '', user_prompt: 'str' = '') -> 'AbstractContextManager[object | None]'",
}
```

Also assert `PhoenixConfig` is frozen and its field order is exactly
`enabled`, `collector_endpoint`, `project_name`, `trace_include_io`,
`max_io_chars`; exercise soft failure for register, span start/set/close,
recording, and flush exceptions; assert exception log messages contain only
exception class names and never exception text, endpoint, prompt, response, or
secret values.

- [ ] **Step 2: Run the focused current-contract tests**

Run:

```text
PYTHONPATH=src python3.10 -m pytest -q tests/test_v01_public_api_contract.py tests/compatibility/test_current_v01_contract.py
```

Expected: PASS. Characterization tests target existing behavior and therefore
need not be forced red when they contain no new helper/production behavior.

- [ ] **Step 3: Write the dependency probe test before its helper**

The subprocess installs an import guard for prefixes
`langchain`, `httpx`, `openai`, `mistral`, `ollama`, `ai_core.runtime`,
`ai_core.client`, and `ai_core.server`, inserts `<repo>/src`, clears provider
credentials from an allowlisted environment, sets `PHOENIX_ENABLED=false`,
imports `ai_core`, runs `init_tracing`, `start_llm_span`,
`record_llm_result`, and `shutdown_tracing`, then prints JSON.

Run the individual test and confirm RED with missing
`run_isolated_import_probe`.

- [ ] **Step 4: Implement the minimal subprocess helper and verify GREEN**

Implement the helper in the test module using only `json`, `os`, `subprocess`,
`sys`, and `pathlib`. Assert return code zero, exact root exports, `tracer is
None`, and no forbidden prefix in imported modules.

Run:

```text
PYTHONPATH=src python3.10 -m pytest -q tests/compatibility/test_dependency_boundary.py
```

Expected: PASS with no network access.

- [ ] **Step 5: Commit Task 1**

```text
git add tests/compatibility
git commit -m "test: lock current tracing compatibility"
```

### Task 2: Immutable version-by-version historical characterization

**Files:**
- Create: `tests/compatibility/git_ref.py`
- Create: `tests/compatibility/ast_contract.py`
- Create: `tests/compatibility/historical_loader.py`
- Create: `tests/compatibility/test_git_ref_helpers.py`
- Create: `tests/compatibility/test_historical_versions.py`
- Create: `tests/fixtures/compatibility/historical_versions.v1.json`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: `read_blob(sha: str, path: str) -> str`,
  `resolve_tag(tag: str) -> str`, `module_contract(source: str) -> dict`, and
  `load_v020_json_client(sha: str) -> tuple[type, object]`.

- [ ] **Step 1: Write failing Git-ref helper tests**

Assert tag peeling matches all four immutable SHAs, `read_blob` returns the
expected version text, paths cannot start with `/` or contain `..`, and missing
objects raise a diagnostic `RefEvidenceError` without fetching.

Run the helper test and confirm RED because `git_ref.py` is absent.

- [ ] **Step 2: Implement exact-object reads and verify GREEN**

Use `git rev-parse <tag>^{commit}` and `git show <40-hex-sha>:<validated-path>`
with `check=True`, captured text, no shell, and repository root discovered from
the test file. Never accept a mutable branch in `read_blob`.

- [ ] **Step 3: Write failing AST contract tests**

Require extraction of literal `__all__`, top-level function signatures,
class methods, enums, dataclass field order/default syntax, and imports. Reject
dynamic/unparseable exports instead of guessing.

- [ ] **Step 4: Implement `module_contract` and verify GREEN**

Use `ast.parse` only. Serialize annotations/defaults with `ast.unparse`; retain
argument kind so keyword-only boundaries are observable.

- [ ] **Step 5: Add the version fixture and version-specific tests**

Record separate objects for v0.1.0, v0.2.0, v0.2.1, and v0.2.2 with exact SHA,
root exports, module set, inference APIs, capabilities, and dependency
families. Tests must establish:

```text
v0.1.0: tracing only, no inference dependencies
v0.2.0: LangChainJsonClient/create_json_completion and hard provider deps
v0.2.1: v0.2 API plus provider/privacy/routing; four observed canonical IDs
v0.2.2: invoke_text/invoke_vision/invoke_pdf_ocr and TEXT/STRUCTURED_JSON/VISION_IMAGE/OCR_PDF; no STT_SEGMENTS
```

Assert each v0.2 root differs from current main and none is represented as a
future normative API.

- [ ] **Step 6: Characterize v0.2.0 fallback with a failing loader test**

Write tests that supply fake `httpx`, LangChain messages/runnable, provider
factory, clock, and model results. Verify lazy provider construction, one
attempt per ready provider, fallback on timeout/transport/429/5xx, terminal
4xx stop, and ordered attempt summaries. First run must fail because
`historical_loader.py` is absent.

- [ ] **Step 7: Implement the isolated loader and verify GREEN**

Build temporary `ai_core` modules from exact Git blobs and controlled
`sys.modules` fakes. Restore `sys.modules` after every load. Never import
provider SDKs or open a socket.

- [ ] **Step 8: Make immutable refs available to CI**

Set `fetch-depth: 0` on `actions/checkout@v4`. Tests themselves never fetch.

- [ ] **Step 9: Run Task 2 and commit**

```text
PYTHONPATH=src python3.10 -m pytest -q tests/compatibility/test_git_ref_helpers.py tests/compatibility/test_historical_versions.py
git add .github/workflows/ci.yml tests/compatibility tests/fixtures/compatibility/historical_versions.v1.json
git commit -m "test: characterize immutable ai-core releases"
```

### Task 3: Consumer evidence and representability fixtures

**Files:**
- Create: `tests/compatibility/fixture_contract.py`
- Create: `tests/compatibility/test_fixture_contract.py`
- Create: `tests/compatibility/test_consumer_contracts.py`
- Create: `tests/fixtures/compatibility/consumer_contracts.v1.json`
- Create: `scripts/verify_consumer_contract_fixtures.py`
- Create: `tests/compatibility/test_workspace_verifier.py`

**Interfaces:**
- Produces: `load_consumer_contracts(path: Path) -> dict`,
  `validate_consumer_contracts(data: object) -> list[str]`, and verifier CLI
  `--workspace-root PATH` returning 0 on exact evidence match and 1 on drift.

- [ ] **Step 1: Write failing fixture-schema tests**

Require top-level `schema_version=1`, exactly nine named consumers, and for each
consumer: provenance entries (`repository`, `sha`, `ref`, `role`, `authority`,
`paths`), five separated evidence/status sections, current path/pin, capability
requirements, three retry levels, fallback owner, privacy, tracing, rollback,
gaps, and risk.

Reject keys/value shapes that resemble credential values, URLs containing
userinfo/query secrets, prompt/schema/payload fields, or an accepted provider
ID outside the four-ID allowlist.

- [ ] **Step 2: Implement fixture validation and verify RED-to-GREEN**

Implement strict standard-library validation. Error messages include fixture
JSON paths but never values suspected to be secrets.

- [ ] **Step 3: Add normalized consumer facts**

Populate synthetic evidence for Prozakupki, KMO, Zoom, Clin-rec, Landing Sell,
agent-lab, Alpha, transcription-service, and image-description-service from the
previous baseline. Mark feature checkouts versus `origin_main`; do not claim
production when authority is `tracked_checkout`. Keep OpenAI, DeepSeek,
Whisper/faster-whisper, Voxtral, extra GPU aliases, and `STT_SEGMENTS` in
observed/governance-pending sections, never accepted IDs.

Media entries must record exact paths, `X-Prozakupki-AI-Key`, contract version
1, 150-second client timeout, retryable/terminal status families, no raw-body
logging, safe default `fake`, durable `max_attempts=3`, and zero implication of
a current canonical server.

- [ ] **Step 4: Add cross-consumer representability tests**

Assert one fallback owner, retry-level separation, explicit old rollback,
model-specific capability evidence, current Alpha no-runtime status, and media
client/server gap. `representable` may be `yes`, `partial`, or `blocked`; a
blocked item requires nonempty gaps and governance questions.

- [ ] **Step 5: Write verifier tests before the verifier script**

Use temporary Git repositories containing tiny synthetic blobs. Verify exact
SHA reads ignore dirty working-tree changes, missing refs fail closed, and no
consumer module is imported/executed.

- [ ] **Step 6: Implement the workspace verifier**

The script imports the test-only fixture validator by repository-relative path,
then performs allowlisted literal/regex assertions against `git -C <repo> show
<sha>:<path>`. It supports only the recorded fact kinds `contains`,
`not_contains`, and `json_or_yaml_literal`; it never prints matched secret
values.

- [ ] **Step 7: Run portable and workspace validation, then commit**

```text
PYTHONPATH=src python3.10 -m pytest -q tests/compatibility/test_fixture_contract.py tests/compatibility/test_consumer_contracts.py tests/compatibility/test_workspace_verifier.py
python3.10 scripts/verify_consumer_contract_fixtures.py --workspace-root /home/kok4444/projects
git add tests/compatibility tests/fixtures/compatibility/consumer_contracts.v1.json scripts/verify_consumer_contract_fixtures.py
git commit -m "test: capture consumer AI requirements"
```

### Task 4: SECRET invariant and draft PR conflict characterization

**Files:**
- Create: `tests/fixtures/compatibility/privacy_conflicts.v1.json`
- Create: `tests/fixtures/compatibility/draft_pr_contracts.v1.json`
- Create: `tests/compatibility/test_privacy_conflicts.py`
- Create: `tests/compatibility/test_draft_pr_contracts.py`

**Interfaces:**
- Consumes: Git-ref helpers and accepted four-ID allowlist.
- Produces: executable desired/observed conflict matrices and five-category PR dispositions.

- [ ] **Step 1: Write the normative SECRET matrix test**

Generate the product of forms `raw/sanitized/surrogated` and boundaries
`local_same_host/external_cloud/unknown_boundary`. Require for every row:
`inference_execution="denied"`, `eligible_routes=0`, `provider_attempts=0`.
Add transitions for alias resolution, sanitization, retry, and fallback and
require that all preserve SECRET denial.

- [ ] **Step 2: Add and test the PR #3 observed conflict**

Use pinned PR #3 source when present to execute only `provider_catalog.py` and
`privacy.py` in isolation. Assert RAW is denied but sanitized/surrogated are
eligible for profiles allowing sanitized data. Cross-check that the conflict
fixture names exactly those differences and keeps the desired invariant denied.
If the commit object is absent, skip only source re-execution; never skip the
portable conflict-matrix assertions.

- [ ] **Step 3: Add draft PR evidence with explicit dispositions**

Every logical block uses exactly one of `KEEP AS-IS`, `KEEP AFTER FIX`,
`SPLIT INTO LATER WP`, `REQUIRES GOVERNANCE DECISION`, or `REJECT / REDESIGN`.
Pin PR numbers/heads and current open/draft/green/no-review state.

Cover PR #3 dependency-light/root compatibility, SECRET, provider hints; PR #4
accepted-ID alias/evidence machinery versus new identities/STT/evidence levels;
PR #5 taxonomy, health/UNKNOWN, ordering, explicit egress, deadline arithmetic
versus enforcement, retry/fallback owner, and absence of executor.

- [ ] **Step 4: Assert governance cannot be broadened by fixtures**

Require accepted provider IDs exact, `STT_SEGMENTS` pending, implementation
authorization false, and every unresolved PR block categorized as governance,
fix, split, or redesign rather than accepted implicitly.

- [ ] **Step 5: Run Task 4 and commit**

```text
PYTHONPATH=src python3.10 -m pytest -q tests/compatibility/test_privacy_conflicts.py tests/compatibility/test_draft_pr_contracts.py
git add tests/compatibility tests/fixtures/compatibility/privacy_conflicts.v1.json tests/fixtures/compatibility/draft_pr_contracts.v1.json
git commit -m "test: expose privacy and draft PR conflicts"
```

### Task 5: Executable changed-path guard

**Files:**
- Create: `scripts/check_characterization_changed_paths.py`
- Create: `tests/compatibility/test_changed_path_guard.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces CLI `--base SHA [--head SHA]` returning 0 only when changed files
  match `.github/workflows/ci.yml`, `tests/**`, `scripts/check_*`,
  `scripts/verify_*`, `docs/**`, with explicit rejection of `src/**`, dependency
  manifests, production config, or any path outside the repository.

- [ ] **Step 1: Write failing guard tests**

Test pure `validate_paths(paths: Iterable[str]) -> list[str]` with permitted
files and rejected `src/ai_core/runtime.py`, `pyproject.toml`, `config/*.yaml`,
absolute paths, and traversal. Test CLI behavior in a temporary Git repo.

- [ ] **Step 2: Implement the minimal guard and verify GREEN**

Use `git diff --name-only <base>...<head>` with argument arrays and validated
40-hex SHAs. Print only rejected paths. Add CI invocation against the merge
base supplied by GitHub or, when unavailable locally, the recorded production
base.

- [ ] **Step 3: Run the guard against this branch and commit**

```text
PYTHONPATH=src python3.10 -m pytest -q tests/compatibility/test_changed_path_guard.py
python3.10 scripts/check_characterization_changed_paths.py --base 7569441c18362cfd15524ad73f56f7f35580c86f --head HEAD
git add scripts/check_characterization_changed_paths.py tests/compatibility/test_changed_path_guard.py .github/workflows/ci.yml
git commit -m "test: enforce characterization-only paths"
```

### Task 6: Technical report and final verification

**Files:**
- Create: `docs/reports/2026-09-09-ai-core-compatibility-characterization-report.md`
- Modify: `docs/superpowers/plans/2026-09-09-ai-core-compatibility-characterization.md` only to mark completed checkboxes if useful.

**Interfaces:**
- Consumes all test output and evidence fixtures.
- Produces the durable decision report and handoff.

- [ ] **Step 1: Run the complete suite twice**

```text
PYTHONPATH=src python3.10 -m pytest -q
PYTHONPATH=src python3.10 -m pytest -q
```

Counts and outcomes must match; record the existing pytest-asyncio warning
separately if still present.

- [ ] **Step 2: Run all safety checks**

```text
python3.10 scripts/verify_consumer_contract_fixtures.py --workspace-root /home/kok4444/projects
python3.10 scripts/check_characterization_changed_paths.py --base 7569441c18362cfd15524ad73f56f7f35580c86f --head HEAD
git diff --check
```

Also scan fixtures for likely credentials, URLs with userinfo/query secrets,
prompt/payload/schema content, nondeterministic sleeps/randomness, and network
client calls.

- [ ] **Step 3: Write the report**

Use the 17 required sections. Include confirmed/refined/refuted baseline facts,
the full version matrix, provenance/authority consumer matrix, SECRET matrix,
five-category PR dispositions, individually answerable governance questions,
validation evidence, branch/base/content head/final-head resolution, risks,
rollback, and one next work package with entry/exit criteria.

- [ ] **Step 4: Verify report and repository state**

Check all claims against fresh command output, scan for placeholders and false
approval language, confirm only permitted paths changed, and confirm the main
checkout still contains the untouched user-owned `.worktrees/` and `uv.lock`.

- [ ] **Step 5: Commit the report**

```text
git add docs/reports/2026-09-09-ai-core-compatibility-characterization-report.md docs/superpowers/plans/2026-09-09-ai-core-compatibility-characterization.md
git commit -m "docs: report compatibility characterization"
```

- [ ] **Step 6: Re-run final verification at final HEAD**

Run the full suite, workspace verifier, changed-path guard, `git diff --check`,
`git status --short --branch`, and `git rev-parse HEAD`. Do not push or merge.
