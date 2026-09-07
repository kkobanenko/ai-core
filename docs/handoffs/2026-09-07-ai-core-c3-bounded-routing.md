# ai-core C3 — bounded routing contracts

## Status

**Branch:** `feat/ai-core-bounded-routing-c3-20260907`  
**Base branch:** `feat/ai-core-consolidation-foundation-20260907`  
**Base SHA:** `4e26d67b825194e489a6a8b553c2a53dfea2a81f`  
**Merge authorization:** **BLOCKED_PENDING_PLATFORM_CONTROL_REVIEW**  
**Review request:** `kkobanenko/platform-control#292`

No consumer repository, dependency, release, tag, deployment, or infrastructure state is changed by C3.

## Goal

Implement the dependency-light bounded-routing contracts already described by the accepted platform-control AI boundary: privacy/capability/health selection, isolated health state, normalized error semantics, and one shared request deadline — while leaving network transports and actual fallback execution for a later optional-transport slice.

## Implemented

### `ai_core.errors`

Normalized error metadata without importing provider SDKs:

- timeout and rate-limit: same-provider retry eligible + fallback eligible;
- HTTP 5xx and transport/connectivity: fallback eligible, but not automatically same-provider retry eligible;
- auth, bad request, and not-found: terminal;
- explicit `RawRouteExhaustedError`, `NoEligibleProviderError`, and `RequestDeadlineExceededError`.

### `ai_core.health`

Dependency-light `ProviderHealthStore`:

- provider health is isolated by canonical provider ID;
- optional model-specific health can block one model without poisoning sibling models;
- provider-level unhealthy state blocks all models for that provider;
- `UNKNOWN` means not observed yet and does not pre-emptively block routing;
- network probes are intentionally **not** in this module and belong to future optional transports.

### `ai_core.routing`

Pure deterministic route planning:

- caller supplies `(provider_id, model)` candidates;
- checks canonical provider existence;
- checks optional authorization whitelist;
- applies privacy eligibility;
- applies explicit model capability registry;
- applies provider/model health;
- sorts by `priority_hint`, provider ID, then model ID;
- returns accepted and rejected candidates with metadata-only rejection reasons;
- sensitive RAW with no eligible provider raises `RawRouteExhaustedError` and requires a **new** SANITIZED/SURROGATED request.

The router does **not** execute calls, retry calls, sanitize payloads, or orchestrate business workflows. This preserves the single-fallback-owner contract.

### `ai_core.budget`

Pure shared-deadline math:

- monotonic absolute deadline;
- remaining-time calculation;
- per-attempt configured timeout cap;
- optional reserve for future provider attempts;
- hard failure when remaining safe budget is below the minimum attempt duration.

Example encoded in tests: 120-second request deadline with one 30-second future reserve gives the first provider at most 90 seconds. If 95 seconds have elapsed, the next provider gets at most 25 seconds.

## Security / compatibility invariants

- uses only the four provider identities already present in foundation;
- root `ai_core.__all__` is untouched;
- no LangChain/httpx/provider SDK dependency is added;
- no network call is implemented;
- no payload, prompt, credential, or response content enters routing metadata;
- sensitive RAW cannot automatically become an external-cloud fallback;
- GPU provider remains `UNKNOWN_BOUNDARY` and cannot receive sensitive RAW under current policy;
- unknown model capabilities fail closed;
- no nested fallback implementation exists in this slice.

## Tests

Target command:

```bash
python -m pytest -q
```

Added coverage includes:

- normalized retry vs fallback semantics;
- provider/model health isolation;
- deterministic provider ordering;
- health-driven candidate exclusion;
- authorization whitelist;
- sensitive RAW exhaustion;
- unknown-model fail-closed behavior;
- 120-second shared deadline + 30-second reserve calculation;
- invalid budget inputs.

Repository CI only triggers on PRs targeting `main`. As with C2, the draft C3 PR may be temporarily retargeted to `main` for CI, receive a synchronize commit, and then be returned to its foundation base. This is validation only and never authorizes merge.

## Risks

1. `UNKNOWN` health currently permits routing. This matches the historical behavior but means health probes should run before strict production routing where required.
2. Error classification uses status attributes/class-name markers to avoid SDK dependencies; optional transports should translate SDK-specific errors into this normalized contract explicitly.
3. Route candidates are caller-provided; policy configuration for building those candidate sets is intentionally deferred and must not become consumer-specific hard-coding inside this router.
4. Deadline budgeting computes safe timeouts but does not enforce cancellation by itself; the future transport executor must honor the returned timeout.
5. Foundation `ProviderProfile.supports_*` booleans are legacy/provider-level hints; routing capability truth is the model-specific capability registry.

## Rollback

C3 is an unmerged branch stacked on the green foundation. Rollback is to close/drop the C3 PR. No production or consumer rollback is necessary because there are no runtime deployments or consumer changes.
