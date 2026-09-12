---
coord_version: 1
state: EXECUTOR_READY
prompt_id: ai-core-s2a-provider-aliases-impl-001
target_repo: kkobanenko/ai-core
target_branch: feat/ai-core-s2a-provider-aliases-20260912
target_worktree: /home/kok4444/projects/ai-core-s2a-provider-aliases-executor
base_sha: f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: src/ai_core/provider_aliases.py, tests/test_s2a_provider_aliases.py, docs/handoffs/2026-09-12-ai-core-s2a-provider-aliases.md
required_paths: src/ai_core/provider_aliases.py, tests/test_s2a_provider_aliases.py, docs/handoffs/2026-09-12-ai-core-s2a-provider-aliases.md
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: "feat: add S2A provider alias contracts"
---

# AI Core S2A — provider aliases only

This is the authorized S2A foundation implementation package.

Authoritative governance is now merged in `kkobanenko/platform-control` PR #302, merge SHA `2d2dd13a1b856ee0e73d6d09355639e6c84910e5`.

Work only in the declared `ai-core` target branch/worktree. Do not modify platform-control or consumer repositories.
Do not create a PR, merge, tag, release, deploy, or trigger hosted CI.
Do not commit or push yourself; Coordinator owns exact-path publication.

## Scope

Implement only deterministic provider alias contracts. No routing, runtime, provider calls, transports, health, retry, fallback, model registry, capability/evidence promotion, trust promotion, service layer, consumer migration, or deployment.

The existing `src/ai_core/provider_catalog.py` remains the canonical identity/boundary contract. Do not modify it unless absolutely required; it is intentionally outside `allowed_paths`, so if you believe it must change, STOP instead of broadening scope.

The current nine-symbol `ai_core` root API must remain unchanged. Do not edit `src/ai_core/__init__.py`.

## Exact authorized aliases

Exactly these five legacy aliases may resolve:

- `ollama_local -> vm100_local_ollama`
- `local_gpu_ollama -> gpu_ollama`
- `local_gpu_vision -> gpu_ollama`
- `mistral -> mistral_external`
- `mistral_ocr -> mistral_external`

Generic `ollama` is intentionally ambiguous and MUST NOT resolve.
Unknown values fail closed.
Do not invent any additional aliases.
Do not perform fuzzy, case-insensitive, whitespace-trimming, prefix, suffix, substring, URL, endpoint, or model-based normalization.

Alias resolution MUST NOT imply or manufacture model identity, model availability, capability, capability evidence, trust, network-boundary promotion, route eligibility, transport, health, retry, fallback, or runtime availability.

## Required implementation

### 1. New module

Create `src/ai_core/provider_aliases.py` as a dependency-light pure contract module.

Preferred contract shape:

- immutable alias mapping (use `MappingProxyType` or equivalent stdlib-only mechanism);
- a specific fail-closed exception such as `UnknownProviderAliasError`;
- `get_provider_aliases()` returning the immutable mapping;
- `resolve_provider_id(value: str) -> str` with this exact deterministic behavior:
  1. if `value` is one of the existing canonical IDs from `provider_catalog.CANONICAL_PROVIDER_IDS`, return it unchanged;
  2. else if `value` is exactly one of the five authorized aliases, return the mapped canonical ID;
  3. else raise the fail-closed alias/identity resolution exception.

Canonical-ID passthrough is identity preservation, not an additional alias mapping.
Do not return `ProviderIdentity`, network boundary, model, capability, route, or runtime objects; return only the canonical provider ID string.

Use the existing provider constants / `CANONICAL_PROVIDER_IDS` from `provider_catalog.py` rather than duplicating canonical identity truth as independent string literals where practical.

Expose only this module's own explicit `__all__`; do not re-export it from package root.

### 2. Tests

Create `tests/test_s2a_provider_aliases.py` with focused tests proving at minimum:

- the alias map contains exactly five entries and exactly the authorized mappings;
- the mapping is immutable;
- every authorized alias resolves to the expected canonical provider ID;
- every canonical provider ID passes through unchanged;
- generic `ollama` fails closed;
- empty string and representative unknown values fail closed;
- near-miss/case/whitespace variants do not normalize silently (examples such as `OLLAMA_LOCAL`, ` ollama_local`, `ollama_local `);
- every successful resolution is one of `CANONICAL_PROVIDER_IDS`;
- no model/capability/routing/runtime semantics are encoded in this module API/data.

Do not weaken existing S1 tests.

### 3. Handoff

Create `docs/handoffs/2026-09-12-ai-core-s2a-provider-aliases.md` containing:

- package name S2A provider aliases;
- branch and base SHA;
- exact five aliases;
- statement that canonical IDs pass through unchanged;
- generic `ollama` and unknown inputs fail closed;
- exact changed files;
- validation performed/results;
- risks/rollback;
- explicit confirmations: root API unchanged, provider catalog unchanged, no routing/runtime/transport/health/retry/fallback, no model/capability/evidence/trust promotion, no consumers, no deployment, no PR, no hosted CI;
- note that Coordinator owns final commit/push SHA.

## Validation

Run locally if shell access is available:

1. `pytest -q tests/test_s2a_provider_aliases.py tests/test_s1_provider_catalog.py tests/test_s1_compatibility_boundary.py tests/test_v01_public_api_contract.py`
2. `git diff --check`

Do not run dependency installation/resolution. Do not run `uv`, `pip`, or `poetry`. If tooling creates `uv.lock` as a side effect, do not edit it; Coordinator owns declared transient handling.

If required behavior cannot be implemented strictly within the three allowed files, STOP and report the blocker. Do not broaden scope.

## Process transition note

This S2A package is intentionally the last package on the old bridge workflow.
After S2A is fully reviewed and merged, the next independent package must be the first Spec Kit-native cycle. Do not start that future package here.

Finish with a concise Executor summary and stop.