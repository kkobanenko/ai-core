# AI Core: current-state and compatibility baseline

**Evidence window:** 2026-09-08–2026-09-09 (Europe/Moscow)

**Repository:** `kkobanenko/ai-core`

**Status:** evidence snapshot; no runtime, consumer, release, tag, or deployment change

## Executive baseline

The production/default baseline before consolidation is `ai-core` `main` at
`7569441c18362cfd15524ad73f56f7f35580c86f`. It is the dependency-light
tracing/configuration line. Its exact root `ai_core.__all__` is:

```text
AttributeValue
PhoenixConfig
init_tracing
load_phoenix_config
maybe_truncate
record_llm_result
sanitize_attributes
shutdown_tracing
start_llm_span
```

Provider execution is **not** present on `main`. The `v0.2.x` tags are a
divergent historical provider line, not ancestors that may be merged or
substituted implicitly. Draft PRs #3–#5 are candidate work, not accepted
architecture. Existing consumers therefore remain on their current paths and
pins until individually approved migration work packages complete.

## Repository state

### Default and historical release lines

| Ref | Peeled SHA | Ancestor of current `main` | Meaning |
|---|---|---:|---|
| `main`, `origin/main` | `7569441c18362cfd15524ad73f56f7f35580c86f` | — | Production/default tracing-only baseline |
| `v0.1.0` | `f7886b51ea4b87b734181a91de06644faaf0ef7e` | yes | Immutable tracing release |
| `v0.2.0` | `e479d0af314714a96c959a2ea677abdcb0942af7` | no | Immutable provider/JSON-fallback release used by Prozakupki |
| `v0.2.1` | `f743057a02a8b69bf943b615510d4745d737e16a` | no | Provider catalog/privacy line used by Landing Sell and agent-lab |
| `v0.2.2` | `679b88fa7cd6e9f64b543c405a90b2ef0dcdc575` | no | Historical multimodal/model-capability line |

The tag SHAs above were resolved with `git rev-parse '<tag>^{}'`; annotated tag
object SHAs are not used. No tag was created, moved, or deleted.

### Relevant branches and draft PRs

| Item | Base | Head | State on evidence date | Disposition |
|---|---|---|---|---|
| PR #3, consolidation foundation | `main@7569441` | `4e26d67b825194e489a6a8b553c2a53dfea2a81f` | open draft; CI run `34155594639` passed; no review decision | blocked; conditional candidate after governance and corrections below |
| PR #4, C2 provider/model evidence | PR #3 `4e26d67` | `1b2569a612968a3ac5099dea955cfccdcb191d52` | open draft; CI run `34156071781` passed; no review decision | blocked; governance-expanding content must be split/deferred |
| PR #5, C3 bounded routing | PR #3 `4e26d67` | `25c269bb93dd37bd9b1556051972f5e1e60b34ad` | open draft; CI run `34156344426` passed; no review decision | blocked; requires policy decisions and contract changes |
| historical provider branch | divergent from `main` | contains `v0.2.x` history | historical evidence only | do not merge wholesale |

Green CI demonstrates only that each draft's own tests pass. It is not
platform-control acceptance and does not make a draft merge-ready.

The documentation work package runs on
`docs/ai-core-transition-baseline-20260908`, based on `7569441`. The primary
checkout's user-owned untracked `.worktrees/` and `uv.lock` were observed and
left unchanged.

## Historical compatibility audit

### `main` / `v0.1.0`

`src/ai_core/__init__.py` preserves the nine-symbol root surface above.
`tests/test_v01_public_api_contract.py` currently verifies:

- exact root export set and absence of the `v0.2` provider exports;
- availability of Zoom's required `record_llm_result` path;
- the safe attribute allowlist and exclusion of secrets/unknown keys;
- deterministic Phoenix defaults and disabled tracing soft-failure;
- disabled-path order isolation, IO truncation, and `AttributeValue` export.

The clean supported local command is:

```text
PYTHONPATH=src python3.10 -m pytest -q
24 passed, 1 pytest-asyncio deprecation warning
```

Plain `python -m pytest -q` used system Python 3.9 and failed during collection
because the source package was not installed. This is an environment/setup
result, not a product regression; the project declares Python `>=3.10`.

### `v0.2.0`

The root surface changes rather than extending `v0.1`: it adds
`ProviderConfig`, `AttemptRecord`, `JsonCompletion`, `LangChainJsonClient`,
`ProviderTransportError`, and `build_chat_model`, but omits v0.1 exports relied
on by tracing consumers, including `record_llm_result`, `sanitize_attributes`,
and `AttributeValue`. It also adds hard LangChain/provider/httpx dependencies.

`LangChainJsonClient` lazily constructs providers, attempts each provider once,
and falls back for timeout, transport, HTTP 429, and HTTP 5xx conditions.
Other 4xx conditions are terminal. JSON/domain schema acceptance remains in
the consumer. These semantics are relevant evidence but are incompatible with
blind replacement of the `main` package.

### `v0.2.1`

This line adds the four accepted provider identities, privacy/egress helpers,
surrogates, DLP, health, and routing around the v0.2 provider API. Its observed
canonical IDs are `vm100_local_ollama`, `gpu_ollama`, `ollama_cloud`, and
`mistral_external`. It still has the v0.2 root/dependency incompatibility with
the main line.

### `v0.2.2`

This line adds model-specific `TEXT`, `STRUCTURED_JSON`, `VISION_IMAGE`, and
`OCR_PDF` capabilities and single-provider vision/PDF helpers. It does not
provide `STT_SEGMENTS`. Its root surface and hard provider dependency set are
larger than both current `main` and `v0.2.0`; it is historical evidence, not an
additive merge candidate.

## Known consumer compatibility boundary

The detailed evidence is in
`docs/architecture/cross_project_ai_inventory.md`. The current boundary is:

| Consumer | Current contract that must not be broken |
|---|---|
| Prozakupki | `v0.2.0`; legacy adapter remains production default; existing provider/model/env/retry/fallback and media paths remain authoritative |
| Zoom | `v0.1.0`; exact tracing imports; consumer-owned raw/LangChain adapters and one fallback loop |
| Clin-rec | no ai-core installation; consumer-owned LangChain provider factory and fallback |
| Landing Sell | `v0.2.1`; ai-core-owned provider fallback, privacy envelope, `RawRouteExhaustedError` |
| agent-lab | `v0.2.1`; provider catalog plus `LangChainJsonClient`, logical aliases and local stand-ins |
| KMO | no ai-core; copied registry and direct HTTP/OpenAI clients with retry/fallback; read-only reference |
| transcription-service | service-local HTTP contract for `/internal/ai/v1/transcriptions`; safe default `fake`; current ai-core has no corresponding server |
| image-description-service | service-local HTTP contract for `/internal/ai/v1/image-descriptions`; safe default `fake`; current ai-core has no corresponding server |
| Alpha University | no ai-core runtime dependency on `main`; accepted narrow-boundary ADR and deterministic Tesseract OCR shadow |

## Compatibility coverage and missing tests

No tests were added in this documentation-only work package. Existing coverage
was inspected and the missing contract layers are prioritized below.

### P0 — required before reconciling any provider foundation

1. **Additive root/API contract.** Define and test the permitted union strategy
   before exposing any new root symbol. Current tests correctly assert the
   v0.2 symbols are absent; they do not define a future compatibility adapter.
2. **Full v0.1 signature/semantic snapshot.** Add `inspect.signature` coverage
   for every public function and data type, enabled-tracing soft-failure,
   shutdown/flush behavior, and metadata-only log/trace safety.
3. **Historical v0.2 characterization.** Test immutable tag behavior in an
   isolated environment: root exports, `ProviderConfig` fields, lazy
   construction, one-attempt-per-provider, fallback classification, and
   terminal error behavior without imposing its dependencies on tracing-only
   imports.
4. **SECRET egress.** Lock the accepted rule that `SECRET` is blocked for all
   providers by default, for `RAW`, `SANITIZED`, and `SURROGATED` forms. PR #3
   only blocks `SECRET + RAW`.
5. **Dependency-light import.** Prove tracing/contracts import and run when
   LangChain, provider SDKs, and httpx are absent.

### P1 — consumer representability fixtures

1. Prozakupki: exact aliases, provider/model records, env precedence,
   timeouts, retry count, fallback order, legacy-default rollback, structured
   JSON failure behavior, and OCR/vision/STT route evidence.
2. KMO: copied registry, default chain, timeout/retry semantics, terminal vs
   fallback errors, and the absence of nested fallback after any future adapter.
3. Zoom: exact v0.1 imports plus raw/LangChain adapter rollback and single
   consumer-owned loop.
4. Clin-rec: package remains uninstalled under its current LangChain
   constraints; its local fallback order is representable without a second
   fallback owner.
5. Landing Sell and agent-lab: exact v0.2.1 imports, privacy exhaustion,
   provider aliases, model aliases, and behavior when ai-core is unavailable.
6. Alpha: narrow boundary and no Planner dependency; any future shadow fixture
   must use a frozen benchmark and require `FALSE_SUPPORTED_COUNT = 0`.

### P2 — deferred service/media contracts

1. Versioned client/server contract tests for transcription and image
   description, including authentication, 4xx/5xx mapping, metadata, global
   deadline composition, and no raw-body logging.
2. Capability evidence levels that distinguish configured, unit-tested,
   integration-tested, and runtime-observed support.
3. `VISION`, `OCR`, and especially `STT_SEGMENTS` remain separate governance
   and implementation work; the present clients do not authorize server work.

## PR #3/#4/#5 assessment

### PR #3 — consolidation foundation

**Aligned:** dependency-light new submodules, exact root API preservation,
model-specific capability profiles, fail-closed unknown models/boundaries,
credential *names* without values, and no transport/runtime/consumer changes.

**Potentially acceptable after governance review:** the four identities already
present in the accepted compatibility matrix and a corrected dependency-light
catalog/capability/privacy foundation.

**Required changes:** block `SECRET` for every outbound form; prevent legacy
provider-level capability booleans from becoming routing truth; add evidence
quality and compatibility characterization; reconcile its authorization claims
with the actual platform-control state.

**Defer:** runtime, transports, executor, service, and consumer adoption.

### PR #4 — C2 provider/model evidence

**Aligned:** explicit alias resolver, ambiguous `ollama` fail-closed behavior,
provider-specific credential env names, and model-scoped capability evidence.

**Potentially acceptable after governance review:** non-expanding alias/evidence
machinery for the four already accepted identities, after evidence levels and
compatibility fixtures are corrected.

**Required changes:** do not label configuration-only observations as proven
runtime capability; validate that `local_gpu_vision -> gpu_ollama` preserves
network identity without erasing consumer semantics; add exact consumer alias
and credential-precedence tests.

**Defer to separate work packages:** proposed `gpu_whisper`,
`openai_external`, and `deepseek_external` identities and all
`STT_SEGMENTS` records. They extend accepted governance and are explicitly out
of scope for this package.

### PR #5 — C3 bounded routing

**Aligned:** dependency-light planning, no network calls/executor, isolated
provider/model health, deterministic output, shared deadline arithmetic, and
explicit raw-route exhaustion.

**Potentially acceptable after governance review:** error descriptors, health
state, route-plan data structures, and deadline math after the policy questions
below are resolved and tested.

**Required changes/decisions:** map its error vocabulary to the transition
taxonomy (`RATE_LIMITED`, policy/egress/privacy/capability/schema errors);
decide whether `UNKNOWN` health is eligible; decide whether caller order or a
global `priority_hint` is authoritative; require fail-closed request-level
authorization for external egress instead of treating `None` as all providers;
inherit the all-form `SECRET` correction from PR #3; add provider-SDK mapping
tests before transports.

**Defer:** retry/fallback executor and every transport/service integration.

PR #4 and PR #5 are parallel stacks on PR #3, not an ordered chain. Neither is
safe to merge independently onto `main`, and none of #3–#5 was merged here.

## Governance status and blockers

The controlling evidence is `platform-control` `origin/main` at
`6445a2ed8614ae0bb663b92413ebf04f3fbc1d99` as inspected during this work
package, rather than the dirty local
checkout or stale observed SHAs embedded in older inventory records.

- `coordination/current-initiative.yaml` classifies `ai-core-v0.3-design` as
  `rfc_only`, with `ai_core_v0_3_implementation_authorized: false` and an
  explicit `ai_core_v0_3_implementation` prohibition.
- The initiative file has `auto_start: false`; its backlog RFC requires a
  separately authorized initiative, an Accepted ADR if the contract changes,
  compatibility-matrix updates, consumer contract tests, and a release plan.
- Accepted ADR-001 currently chooses the narrower tracing plus optional
  provider/transport-primitives boundary. Product orchestration/domain/schema
  validation remain consumer-owned; one fallback owner is mandatory and
  nested fallback is forbidden.
- The accepted matrix names only four provider identities. New identities and
  `STT_SEGMENTS` are not accepted by this work package.
- PR bodies reference platform-control PRs #293, #291, and #292 respectively.
  Direct queries found no resolvable PRs with those numbers; the observed PR
  list ended at #287. A later retry was blocked by the sandbox proxy. The
  reviews are therefore **absent/unverifiable**, never accepted.
- The transition plan's fuller future runtime/service ownership is a desired
  direction, not implementation authorization and not a silent supersession of
  ADR-001.
- No `pending_decision` was resolved. No deployment lock was needed because no
  infrastructure action occurred.

## Stop boundary

The next implementation action must stop until platform-control records a
real review/decision and the P0 compatibility-test package exists. Current
consumers, release pins, old fallback paths, provider identities, and media
capabilities remain unchanged and authoritative for their own execution paths.
