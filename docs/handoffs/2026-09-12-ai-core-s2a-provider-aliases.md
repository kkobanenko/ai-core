# AI Core S2A Provider Aliases Handoff

**Date:** 2026-09-12
**Status:** implementation complete; Coordinator publication pending

## Package

S2A provider aliases — deterministic legacy alias contracts only.

## Governance and Git

- AI Core branch: `feat/ai-core-s2a-provider-aliases-20260912`
- AI Core base SHA: `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e`
- Authoritative platform-control merge SHA: `2d2dd13a1b856ee0e73d6d09355639e6c84910e5`
- Coordinator owns final commit/push SHA.

## Authorized aliases

Exactly five legacy aliases resolve deterministically:

- `ollama_local` → `vm100_local_ollama`
- `local_gpu_ollama` → `gpu_ollama`
- `local_gpu_vision` → `gpu_ollama`
- `mistral` → `mistral_external`
- `mistral_ocr` → `mistral_external`

Canonical provider IDs from `provider_catalog.CANONICAL_PROVIDER_IDS` pass
through unchanged. Generic `ollama` and all unknown inputs fail closed via
`UnknownProviderAliasError`. No normalization of case, whitespace, prefix,
suffix, substring, URL, endpoint, or model values is performed.

## Changed files

- `src/ai_core/provider_aliases.py`
- `tests/test_s2a_provider_aliases.py`
- `docs/handoffs/2026-09-12-ai-core-s2a-provider-aliases.md`

## Validation

Local checks requested by the work package:

1. `pytest -q tests/test_s2a_provider_aliases.py tests/test_s1_provider_catalog.py tests/test_s1_compatibility_boundary.py tests/test_v01_public_api_contract.py`
2. `git diff --check`

Executor environment rejected shell access during this run, so the above
commands were not executed here. Coordinator must re-run both checks on the
publication worktree before merge authorization.

## Explicit confirmations

- Root `ai_core.__all__` unchanged; no re-export from package root.
- `provider_catalog.py` unchanged.
- No routing, runtime, transport, health, retry, or fallback behavior added.
- No model, capability, evidence, or trust promotion encoded in alias data/API.
- No consumer migration, deployment, PR creation, merge, tag, release, or
  hosted CI triggered by this package.
- No additional aliases invented beyond the authorized five.

## Risks

- Alias resolution is identity normalization only; it does not imply provider
  availability, model identity, capability, route eligibility, or runtime
  readiness.
- Consumers that still emit generic `ollama` must migrate separately; this
  package intentionally rejects that value.
- Near-miss strings fail closed; callers must pass exact alias or canonical ID
  values.

## Rollback

Before publication merge, drop the branch/worktree changes for
`feat/ai-core-s2a-provider-aliases-20260912`. AI Core main and consumers need
no rollback until a publication commit is merged.

If later merged, rollback requires a separately reviewed revert of the three
S2A files only; do not rewrite main or existing tags.
