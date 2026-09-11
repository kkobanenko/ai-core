# AI Core S1 Foundation Contracts Handoff

**Date:** 2026-09-11
**Status:** implementation complete; draft review pending

## Governance and Git

- Authoritative platform-control:
  `main@c78b5e735d9b47e6550f2f6f7df084406c3ecfe0`
- Authoritative work package: `S1_foundation_contracts`
- Scope: `FOUNDATION_ONLY`
- AI Core branch: `feat/ai-core-s1-foundation-contracts-20260911`
- AI Core base: `7569441c18362cfd15524ad73f56f7f35580c86f`
- Pre-handoff implementation head:
  `2531d916cd4cb2c40af44acf63f86488bb60817c`
- Draft PR: assigned during publication and recorded in the bridge closeout

The broad `ai_core_v0_3_implementation_authorized` flag remains false. This
work does not authorize merge of its future draft PR.

## Delivered contracts

### Provider identity

`ai_core.provider_catalog` exposes exactly four accepted IDs and immutable
identity-to-network-boundary metadata:

- `vm100_local_ollama` → `LOCAL_SAME_HOST`
- `gpu_ollama` → `UNKNOWN_BOUNDARY`
- `ollama_cloud` → `EXTERNAL`
- `mistral_external` → `EXTERNAL`

Unknown identities raise `UnknownProviderIdentityError`. The returned catalog
is read-only. It contains no endpoint, credential, backend, health, cost,
latency, priority, model, or capability metadata.

### Capability evidence

`ai_core.capabilities` provides pure capability and evidence vocabulary. Every
record is scoped to provider identity, model, capability, network boundary,
and one of the five governed evidence levels. Unknown providers, invalid
vocabulary values, empty subjects, and boundary drift are rejected.

`has_runtime_observation()` is true only for `RUNTIME_OBSERVED`; its result is
explicitly not routing or production eligibility. There is no concrete model
registry. `FAILED_INCONCLUSIVE` does not promote evidence. `STT_SEGMENTS` is
absent.

### Privacy and egress

`ai_core.privacy` provides the governed data-class and outbound-form
vocabulary plus a pure pre-routing predicate.

- `SECRET` is denied for all three forms across all three boundaries.
- Sanitization and surrogation cannot change a SECRET classification.
- External and unknown-boundary egress require request authorization.
- Authorization accepts only literal `True`; truthy objects fail closed.
- Non-enum contract values fail closed.
- Provider/catalog membership is not an egress input and cannot grant access.

## Compatibility boundary

- `ai_core.__all__` remains the exact existing nine symbols.
- New APIs require explicit submodule imports.
- Importing current tracing does not import foundation modules or provider
  libraries.
- `pyproject.toml` is unchanged; no dependency or lock-file change exists.
- No existing production source file was modified.

## PR #3 provenance and disposition

Read-only donor evidence came from PR #3 head
`4e26d67b825194e489a6a8b553c2a53dfea2a81f`. No commit was cherry-picked.

Reimplemented ideas:

- separate canonical provider constants;
- immutable identity records and fail-closed lookup;
- model-scoped capability vocabulary;
- data-class and outbound-form vocabulary;
- explicit submodule-only APIs.

Redesigned semantics:

- provider profiles were reduced to identity and governed boundary only;
- `EXTERNAL_CLOUD`/extra trust states were aligned to authoritative
  `EXTERNAL`, `LOCAL_SAME_HOST`, and `UNKNOWN_BOUNDARY`;
- capability booleans/concrete model profiles became pure evidence types with
  no automatic capability or route promotion;
- transformed SECRET eligibility was replaced by all-form denial;
- provider-level PII policy was replaced by explicit request-level egress
  authorization.

Excluded:

- endpoint and credential environment names/defaults;
- backend/health/cost/latency/priority metadata;
- concrete model profiles;
- aliases;
- route planner, health state, deadlines, retry/fallback executor;
- runtime, transports, service, consumers, and new provider identities.

## Test evidence

- Baseline before S1: **24 passed** on Python 3.10.
- Final AI Core suite: **71 passed** on Python 3.10.
- Existing read-only characterization suite with S1 first in `PYTHONPATH`:
  **77 passed**.
- Pinned consumer verifier: **9 contracts verified**.
- `python3.10 -m compileall -q src`: pass.
- `git diff --check`: pass.
- Python 3.12 is unavailable locally; the existing hosted workflow uses Python
  3.12 and must be green on the final PR head.

The local environment emits an existing `pytest-asyncio` configuration
deprecation warning. It does not affect outcomes and no dependency/config
change was made to suppress it.

## Explicitly untouched

- AI Core root exports and existing tracing/config/attribute/IO behavior.
- AI Core main, releases, and tags.
- AI Core PR #3, #4, and #5 branches, metadata, and history.
- All consumer repositories.
- Runtime, service, provider transports/calls, executor, retry/fallback
  execution, routing, health, and deadline behavior.
- Infrastructure and deployment.

## Risks and blockers

- Contracts are not runtime enforcement; consumers remain responsible for
  their current behavior until separately governed migration.
- Network boundaries are the current governance snapshot. GPU stays unknown.
- No concrete capability record is shipped, so S1 cannot establish that any
  provider/model route is production eligible.
- Downstream adoption and aliases are deferred.
- Merge remains blocked pending external review, exact-head hosted CI, and
  separate operator merge authorization.

## Rollback

Before merge, close the draft PR and drop branch/worktree
`feat/ai-core-s1-foundation-contracts-20260911`. AI Core main and consumers need
no rollback.

If later merged, rollback requires a separately reviewed revert; never rewrite
main or existing tags.
