# AI Core Compatibility Characterization Report

**Date:** 2026-09-09  
**Result:** EVIDENCE + EXECUTABLE COMPATIBILITY SAFETY NET  
**Implementation authorization:** **NO**

## 1. Executive summary

This work package created an executable boundary around the current
tracing-only `ai-core`, four immutable release tags, nine material consumers,
the all-form `SECRET` invariant, and draft PR #3–#5. It changed no production
module, dependency manifest, consumer, provider identity, runtime, service,
transport, infrastructure, release, tag, or `main`.

The safety net now proves:

- current `main` keeps its exact nine-symbol root API, signatures, frozen
  configuration shape, soft-fail tracing, metadata-only default, and
  dependency-light import;
- `v0.1.0`, `v0.2.0`, `v0.2.1`, and `v0.2.2` are separate observed historical
  contracts, not one future API and not drop-in replacements for `main`;
- the `v0.2.0` fallback client is lazy, tries each ready provider once, falls
  through on timeout/transport/429/5xx, and stops on other 4xx;
- all nine consumers have provenance-backed, content-free infrastructure
  requirements that can be checked against exact Git objects;
- `SECRET` must produce no eligible route and zero provider attempts for every
  form and boundary, while PR #3 currently violates that contract for
  `SANITIZED` and `SURROGATED`;
- PR #3–#5 contain useful pieces, but none is merge-ready and all unresolved
  blocks have an explicit disposition.

The complete suite passed twice with the same count: **101 passed**. The
workspace verifier confirmed all nine pinned consumer contracts. The
changed-path guard confirmed characterization-only changes.

It is safe to proceed to an external architecture/governance review and PR
decomposition package. It is **not** safe or authorized to begin runtime,
transport, executor, service, or consumer migration work.

### Previous baseline reconciliation

Confirmed:

- production baseline is
  `main@7569441c18362cfd15524ad73f56f7f35580c86f` and is tracing-only;
- historical v0.2 roots and hard dependencies diverge from current `main`;
- Prozakupki uses an optional `v0.2.0` path with legacy default; Zoom uses
  `v0.1.0`; Landing Sell and agent-lab use `v0.2.1`; KMO and Clin-rec own local
  implementations;
- the two media services have clients but current ai-core has no server;
- Alpha main has no ai-core/LLM runtime dependency;
- PR #3–#5 remain draft/green/unreviewed and platform-control implementation
  authorization remains false.

Refined:

- successful `v0.2.0` fallback returns ordered attempt summaries, but exhausted
  fallback raises `ProviderTransportError` without exposing the accumulated
  attempt summary to the caller;
- consumer facts from tracked feature checkouts are explicitly separated from
  `origin/main` authority;
- the ordering in PR #3's catalog is an observed insertion order, not an
  approved route order.

Refuted:

- the early characterization plan mentioned a historical `invoke_text` in
  `v0.2.2`. Exact source inspection proves that `v0.2.2` has
  `LangChainJsonClient.create_json_completion`, `invoke_vision`, and
  `invoke_pdf_ocr`, but **no `invoke_text`**. The fixture and test preserve the
  observed fact rather than the assumption.

The user-provided baseline copy under
`docs/tmp/ai-core-transition-baseline-20260908` was read-only checked. SHA-256
digests of its six required baseline documents exactly match the committed
documents used by this branch. Nothing under `docs/tmp/` was modified.

## 2. Repository state

| Item | Value |
|---|---|
| Repository | `kkobanenko/ai-core` |
| Branch | `test/ai-core-compatibility-characterization-20260909` |
| Production base | `7569441c18362cfd15524ad73f56f7f35580c86f` |
| Documentation parent | `65a865e5eef38e44559d98ab9187d5d59b8fa2e7` |
| Pre-report content head | `744eed0659aa8e98fb4a37c35692c96831ec7023` |
| Delivery head | resolve with `git rev-parse HEAD`; reported in final handoff |
| Worktree | `/home/kok4444/projects/ai-core/.worktrees/compatibility-characterization-20260909` |
| Upstream | `origin/test/ai-core-compatibility-characterization-20260909` |

Pre-report comparison against the production base contains 32 paths, all
within the approved boundary. Changes are limited to:

- `.github/workflows/ci.yml`: full-history checkout plus a guard scoped to this
  characterization branch;
- `tests/compatibility/**`: contract tests and test-only helpers;
- `tests/fixtures/compatibility/**`: versioned synthetic/reference evidence;
- `scripts/check_characterization_changed_paths.py` and
  `scripts/verify_consumer_contract_fixtures.py`;
- the previously approved baseline/design/plan Markdown and this report.

No `src/ai_core/**`, `pyproject.toml`, production configuration, consumer file,
or platform-control file changed. The primary checkout remains on
`main...origin/main` with the pre-existing untracked `.worktrees/`, `docs/tmp/`,
and `uv.lock`; none was modified or deleted by this worktree.

## 3. Current v0.1 contract

The current root exports exactly:

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

Exact callable signatures are locked:

| Symbol | Signature |
|---|---|
| `init_tracing` | `(project_name: str | None = None) -> object | None` |
| `load_phoenix_config` | `() -> PhoenixConfig` |
| `maybe_truncate` | `(text: str | None, max_chars: int) -> str | None` |
| `record_llm_result` | `(span, *, response_text='', status, latency_ms=None, fallback_mode=None, error_type=None) -> None` |
| `sanitize_attributes` | `(attributes: Mapping[str, object] | None) -> dict[str, AttributeValue]` |
| `shutdown_tracing` | `() -> None` |
| `start_llm_span` | `(*, workflow, attributes=None, system_prompt='', user_prompt='') -> AbstractContextManager[object | None]` |

`PhoenixConfig` is frozen and its field order is exactly `enabled`,
`collector_endpoint`, `project_name`, `trace_include_io`, `max_io_chars`.

Behavioral characterization confirms:

- disabled tracing is a no-op and returns `None`;
- Phoenix registration, span creation, attribute recording, and flush failures
  are soft failures;
- warnings may contain the exception class but not exception text, endpoint,
  credential-like content, prompts, or responses;
- IO capture is off by default;
- only allowlisted metadata reaches the span; an `api_key` attribute is dropped;
- shutdown remains safe when no provider exists or flush fails.

The current package has one runtime dependency,
`arize-phoenix-otel==0.16.1`. An isolated Python process actively rejects
LangChain, httpx, provider SDKs, and future `ai_core.runtime/client/server`
imports while importing and exercising the root tracing API. It passes without
loading any forbidden module.

Primary compatibility risk: importing a historical v0.2 root or dependency
bundle wholesale would remove current exports and force inference dependencies
onto tracing-only consumers.

## 4. Historical v0.2.x findings

All rows below are `OBSERVED_HISTORICAL_EVIDENCE`; none is a normative future
API.

| Tag | Exact SHA | Modules / root exports | Inference surface | Dependency boundary | Compatibility finding |
|---|---|---:|---|---|---|
| `v0.1.0` | `f7886b51ea4b87b734181a91de06644faaf0ef7e` | 5 / 9 | none | Phoenix OTEL only | tracing evidence; same role as current line |
| `v0.2.0` | `e479d0af314714a96c959a2ea677abdcb0942af7` | 8 / 12 | `LangChainJsonClient.create_json_completion` | Phoenix, OTEL, four pinned LangChain/provider packages, httpx | Prozakupki evidence; incompatible root/dependency replacement |
| `v0.2.1` | `f743057a02a8b69bf943b615510d4745d737e16a` | 14 / 44 | v0.2.0 client plus provider/privacy/routing/health | same hard v0.2 bundle | Landing Sell/agent-lab evidence; four observed IDs |
| `v0.2.2` | `679b88fa7cd6e9f64b543c405a90b2ef0dcdc575` | 21 / 63 | JSON client, `invoke_vision`, `invoke_pdf_ocr`; no `invoke_text` | same hard v0.2 bundle | media evidence only; no `STT_SEGMENTS` |

Stable v0.2 record shapes are also locked: `ProviderConfig`, `AttemptRecord`,
and `JsonCompletion` retain the same field order across all three v0.2 tags.

The isolated `v0.2.0` harness proves:

- provider objects are constructed only during invocation;
- unready providers are filtered and each ready provider is attempted once;
- Python timeout, httpx timeout/transport, HTTP 429, and HTTP 500–599 advance;
- HTTP 400/401/403/404/422 stop the chain;
- successful results preserve provider/model/token data and ordered attempt
  summaries;
- response content is returned raw; domain/JSON acceptance is not performed;
- exhausted fallback raises the final historical `ProviderTransportError` and
  does not attach the accumulated attempt summary.

Potentially reusable later: record shapes, lazy construction, explicit
fallback classification, model-scoped capabilities from v0.2.2, and
single-provider media primitives. They must be generalized behind an additive,
dependency-light contract. The v0.2 roots, hard dependency bundle,
provider-level truth assumptions, and historical privacy rule must not be
copied directly.

## 5. Consumer compatibility matrix

The portable fixture contains infrastructure facts only. Provider/model names
found in a consumer remain observations, not entries in a hidden canonical
registry.

| Consumer | Provenance / authority | Current path | Required capabilities | Critical semantics | Representable? | Gaps | Risk |
|---|---|---|---|---|---|---|---|
| Prozakupki | `70f9cf0`, tracked feature checkout | legacy default; optional `v0.2.0` adapter | text/JSON; configured vision/OCR/STT | path-dependent retry/fallback; product validation; `AI_ADAPTER=legacy` rollback | partial | fallback owner varies; media not accepted shared contract | very high |
| KMO | `31f6f9b`, tracked `main`, read-only reference | copied registry/direct clients/retry/fallback | text/JSON; image-description path | consumer owns order, retry and fallback | partial | aliases/credential precedence product-specific; privacy unproven | very high |
| Zoom | `90f0665`, tracked checkout | raw Ollama default; LangChain adapter; `v0.1.0` tracing | text/JSON | exact tracing imports; one consumer failover loop; raw rollback | partial | future fallback owner undecided | high |
| Clin-rec | `950a21c`, tracked checkout | local LangChain factory; no ai-core | structured clinical output | consumer order/domain validation; fallback on timeout/429/5xx | partial | LangChain `<1` conflicts with historical v0.2 bundle | high |
| Landing Sell | `5645cd8`, tracked feature checkout; matrix exception | privacy envelope to `v0.2.1` gateway | text/JSON | ai-core owns fallback; fail-closed raw exhaustion; pinned rollback | partial | historical all-form SECRET conflict | high |
| agent-lab | `c87b3e9`, tracked `main` | `v0.2.1` adapter plus product model aliases | text/JSON; configured vision model | ai-core owns chain; local stand-ins on import failure | partial | stand-ins mask incompatibility; vision config is not proof | medium-high |
| Alpha University | `7216b37`, `origin/main` | deterministic Planner and Tesseract OCR shadow | deterministic OCR only | no ai-core/LLM runtime; narrow accepted boundary | yes, current state | none for current path | low current |
| transcription-service | `067a0f2`, `origin/main` | safe `fake` default; optional HTTP client | proposed `STT_SEGMENTS` | contract v1; 150 s client timeout; no raw-body logs; durable attempts 3 | blocked | no server; capability unaccepted; auth/deployment owner open | high/blocking |
| image-description-service | `0d6b795`, `origin/main` | safe `fake` default; optional HTTP client | vision image description | contract v1; 150 s client timeout; no raw-body logs; durable attempts 3 | blocked | no server; capability evidence/auth/deployment open | high/blocking |

The workspace verifier reads only `git show <exact-sha>:<path>`. It confirmed
all nine records even when repositories are mounted through workspace
symlinks. Dirty working-tree files are ignored and consumer Python modules are
never imported.

The two HTTP clients expect:

- `/internal/ai/v1/transcriptions` or
  `/internal/ai/v1/image-descriptions`;
- `X-Prozakupki-AI-Key` service authentication;
- response contract version 1;
- 150-second client timeout;
- transport/429/5xx retryable and ordinary 4xx terminal classifications;
- no raw response body in logs/errors;
- consumer durable `max_attempts=3`, which is not a provider-attempt policy.

These are consumer requirements only. They do not prove or authorize a
canonical AI Core service.

## 6. Privacy findings

The normative safety matrix is machine-locked as follows:

| Outbound form | Local same host | External cloud | Unknown boundary |
|---|---|---|---|
| `RAW` | denied / 0 routes / 0 attempts | denied / 0 routes / 0 attempts | denied / 0 routes / 0 attempts |
| `SANITIZED` | denied / 0 routes / 0 attempts | denied / 0 routes / 0 attempts | denied / 0 routes / 0 attempts |
| `SURROGATED` | denied / 0 routes / 0 attempts | denied / 0 routes / 0 attempts | denied / 0 routes / 0 attempts |

Alias resolution, sanitization, retry, and fallback are required to preserve
the denial. A transformed representation does not silently reclassify
`SECRET`.

Current `main` has no production privacy module, so this is a desired safety
contract, not an implementation change. Exact execution of the dependency-light
PR #3 modules shows:

- `SECRET + RAW`: no eligible provider;
- `SECRET + SANITIZED`: all four catalog profiles eligible;
- `SECRET + SURROGATED`: all four catalog profiles eligible.

Therefore the PR #3 policy block is `REJECT / REDESIGN`. The contradiction is
represented by a passing characterization test and has not been patched or
weakened in production.

## 7. Dependency boundary findings

| Layer | Observed/required dependency rule |
|---|---|
| Current tracing-only root | Phoenix OTEL only; no LangChain, httpx, provider SDK, client, server, or runtime import |
| Historical v0.2 inference | hard LangChain core/Ollama/Mistral/OpenAI plus httpx and OTEL bundle |
| Future optional transports | must remain outside tracing imports and should be optional extras; not implemented here |
| Future thin client/service | no current canonical module or dependency exists; media clients cannot define the server by themselves |

Clin-rec demonstrates why the boundary matters: its LangChain `<1` family is
incompatible with the exact historical v0.2 provider packages. Zoom combines
`v0.1.0` tracing with a consumer-owned LangChain adapter and must not inherit
the v0.2 bundle. Any future root expansion requires an additive compatibility
decision and isolated dependency tests.

## 8. PR #3 assessment

Fresh state: OPEN, DRAFT, CI success, no reviews; head
`4e26d67b825194e489a6a8b553c2a53dfea2a81f`, base production main.

| Logical block | Disposition | Required action |
|---|---|---|
| Dependency-light new submodules and unchanged root | `KEEP AS-IS` | preserve the import/root boundary |
| No runtime, transport, service, or consumer change | `KEEP AS-IS` | keep foundation-only |
| Four-ID catalog | `REQUIRES GOVERNANCE DECISION` | accept only after real platform review; do not infer merge authorization |
| `SECRET` after sanitization/surrogation | `REJECT / REDESIGN` | enforce denial before route construction for every form |
| Provider-level capability hints | `KEEP AFTER FIX` | prevent hints from becoming model routing truth; attach evidence level |

Recommended action: keep draft. Rework the privacy rule and capability/evidence
semantics in a fresh, reviewable stack after governance records the permitted
foundation scope. Do not merge the current head.

## 9. PR #4 assessment

Fresh state: OPEN, DRAFT, CI success, no reviews; head
`1b2569a612968a3ac5099dea955cfccdcb191d52`, stacked on PR #3 head.

| Logical block | Disposition | Required action |
|---|---|---|
| Fail-closed alias resolver limited to accepted identities | `KEEP AFTER FIX` | retain ambiguity failure; add exact consumer alias/precedence fixtures |
| Model-scoped evidence levels | `KEEP AFTER FIX` | distinguish configured, tested, integrated, and runtime-observed evidence |
| `gpu_whisper`, `openai_external`, `deepseek_external` | `SPLIT INTO LATER WP` | require individual identity/privacy/credential governance |
| `STT_SEGMENTS` | `SPLIT INTO LATER WP` | separate capability evidence and service-contract decision |
| Configuration labeled as proven runtime capability | `REJECT / REDESIGN` | downgrade evidence until tested/observed |

Recommended action: split. Rebase only non-expanding alias/evidence machinery
for the accepted four identities after PR #3 is corrected. Leave every new
identity and STT record out of the candidate foundation PR.

## 10. PR #5 assessment

Fresh state: OPEN, DRAFT, CI success, no reviews; head
`25c269bb93dd37bd9b1556051972f5e1e60b34ad`, independently stacked on PR #3.
Its new planning modules contain no httpx/requests transport execution.

| Logical block | Disposition | Required action |
|---|---|---|
| Deterministic deadline arithmetic | `KEEP AS-IS` | retain as pure calculation |
| Error descriptors | `KEEP AFTER FIX` | map to canonical policy/privacy/capability/schema/rate-limit taxonomy |
| `UNKNOWN` health eligibility | `REQUIRES GOVERNANCE DECISION` | decide fail-closed versus bounded exploratory eligibility |
| Caller order vs global `priority_hint` | `REQUIRES GOVERNANCE DECISION` | name the authoritative order and tie-break rules |
| Missing explicit egress allowlist means all providers | `REJECT / REDESIGN` | require request-level authorization; absence must fail closed |
| Inherited all-form SECRET behavior | `REJECT / REDESIGN` | eliminate all transformed-state bypasses |
| Planning objects without network execution | `KEEP AFTER FIX` | retain only after the policy decisions above are encoded |
| Retry/fallback executor and transports | `SPLIT INTO LATER WP` | requires separate authorization and single-owner contract |

Deadline arithmetic is not enforcement. A later executor must prove that
provider timeout, retry delay, fallback, and caller deadline compose without
exceeding one shared deadline. PR #5 currently does not and should not supply
that executor.

## 11. Test suite added

| Group | Protection | Regressions detected |
|---|---|---|
| Current v0.1 contract | exact signatures, types, soft failure, safe logging/IO | root/signature drift, leaked content, hard tracing failures |
| Dependency subprocess | tracing without inference dependencies | accidental LangChain/httpx/SDK/runtime imports |
| Git-ref/AST helpers | exact local objects and static API extraction | tag drift, mutable refs, unsafe paths, guessed dynamic exports |
| Historical versions | per-tag modules/exports/dependencies/types/capabilities | blending v0.2 versions or treating them as future API |
| Historical loader | real v0.2.0 fallback semantics with fakes | eager clients, duplicate attempts, wrong retry class, hidden validation |
| Fixture validator | nine consumers, provenance, separated evidence states | hidden registry expansion, content/credential values, missing rollback |
| Workspace verifier | exact consumer Git evidence | dirty checkout authority, missing refs, executed consumer code |
| Consumer invariants | retry-level separation and representability | nested fallback assumptions, media client mistaken for server |
| Privacy conflict | all-form/all-boundary SECRET and PR #3 execution | alias/transformation/retry/fallback privacy bypass |
| Draft PR contracts | pinned heads and five dispositions | implicit governance acceptance or scope mixing |
| Changed-path guard | characterization-only branch diff | production/runtime/manifest/config changes |

All historical and PR execution uses local Git blobs and fakes. No provider SDK
is installed for the harness, no socket is opened, and no provider is called.

## 12. Validation results

Executed from the compatibility worktree with Python 3.10:

```text
PYTHONPATH=src python3.10 -m pytest -q
101 passed in 2.68s

PYTHONPATH=src python3.10 -m pytest -q
101 passed in 1.43s

python3.10 scripts/verify_consumer_contract_fixtures.py \
  --workspace-root /home/kok4444/projects
verified 9 pinned consumer contracts

python3.10 scripts/check_characterization_changed_paths.py \
  --base 7569441c18362cfd15524ad73f56f7f35580c86f \
  --head 58c1e3ba40d5ba4093664d97ffb6daa45f06df09
verified 32 characterization-only changed paths

git diff --check
PASS
```

The changed-path guard will be rerun at final HEAD. Both suite runs emitted one
pre-existing `pytest-asyncio` deprecation warning about unset
`asyncio_default_fixture_loop_scope`; it did not change counts or outcomes.

Additional checks:

- fixture scan found no credential-shaped value or URL with userinfo/query
  secrets;
- fixture-key scan found no prompt, payload, schema, credential, password,
  secret-value, or token field;
- network/nondeterminism scan found no requests client, urllib/socket call,
  wall-clock sleep, or random choice in the added tests/scripts;
- exact Git object tests peel all four tags to recorded SHAs;
- the six requested baseline documents in `docs/tmp/...` and the committed
  branch copies have matching SHA-256 digests;
- fresh GitHub queries on 2026-09-09 confirmed PR #3–#5 heads/state/checks and
  empty review lists;
- fresh GitHub queries could not resolve platform-control PR #291, #292, or
  #293; these are absent/unverifiable, not approvals;
- primary checkout state and user-owned untracked paths remain unchanged.

## 13. Open questions / governance decisions

Each item requires an independently recorded answer:

1. Does an accepted successor to ADR-001 authorize any v0.3 production
   foundation, or does option 2 remain the complete boundary?
2. Is the all-form rule `SECRET -> denied -> zero routes -> zero attempts`
   confirmed as the only permitted default at every boundary?
3. May PR #3 expose a provider catalog limited to the four existing IDs, and
   through which non-root namespace?
4. What evidence levels are required before a model capability may affect
   routing: configured, unit-tested, integration-tested, or runtime-observed?
5. What is the resolved network boundary of `gpu_ollama`; until then, is all
   sensitive raw egress explicitly denied?
6. Are any of `gpu_whisper`, `openai_external`, or `deepseek_external` accepted
   as canonical identities? This package assumes no.
7. Is `STT_SEGMENTS` accepted, with which model evidence and data-handling
   policy? This package assumes no.
8. Is an AI Core HTTP service part of the accepted architecture, and who owns
   service authentication, credentials, deployment, and payload sanitation?
9. Is request-supplied provider order authoritative, or is global catalog
   priority authoritative? What are deterministic tie-break rules?
10. Is `UNKNOWN` health eligible for a route, and under which explicit request
    policy?
11. Must missing request-level egress authorization mean no external routes?
12. What canonical error taxonomy separates privacy/policy, capability,
    authentication, rate limit, transport, provider, schema, and deadline?
13. For each consumer, who owns provider-call retry and provider fallback, and
    how is nested fallback mechanically prevented?
14. How must one shared deadline bound attempt timeout, retry delay, fallback,
    service overhead, and caller timeout?
15. Are the two existing HTTP client shapes adopted, revised, or kept purely
    consumer-local until a separate service ADR?

Current platform-control evidence remains
`origin/main@6445a2ed8614ae0bb663b92413ebf04f3fbc1d99` with `kind: rfc_only`,
`auto_start: false`, `ai_core_v0_3_implementation_authorized: false`, and an
explicit `ai_core_v0_3_implementation` prohibition. No pending decision was
resolved here.

## 14. Risks

- **Root/API:** merging a v0.2 line wholesale breaks v0.1 tracing imports.
- **Dependencies:** hard provider bundles can conflict with Clin-rec and burden
  tracing-only consumers.
- **Privacy:** PR #3 permits transformed SECRET egress; aliases, retry, or
  fallback could amplify the bypass if denial occurs too late.
- **Fallback:** multiple owners multiply attempts, cost, latency, and error
  transformations.
- **Evidence:** configuration-only model records can falsely authorize media
  or STT behavior.
- **Identity:** ambiguous `ollama`/GPU aliases can erase physical boundary and
  privacy meaning.
- **Ordering:** catalog insertion order, priority hints, and consumer order are
  currently different concepts that can be mistaken for one policy.
- **Deadlines:** pure budget arithmetic can be mistaken for actual enforcement.
- **Service:** media clients can be mistaken for a deployed canonical server;
  switching away from `fake` would fail today.
- **Provenance:** feature checkout evidence can be mislabeled as production if
  authority fields are ignored.
- **Operations:** provider credentials, service auth, deployment owner, and
  infrastructure locks remain unresolved.

## 15. Recommended target architecture refinements

Only evidence-supported refinements are recommended:

1. Keep current root API and tracing imports unchanged; place future contracts
   under additive submodules after a compatibility decision.
2. Keep tracing dependency-light. Put each provider transport behind optional
   dependencies and test that importing contracts never imports transports.
3. Treat immutable v0.2 releases as compatibility adapters/evidence, not the
   source tree for a new main line.
4. Separate provider identity, model identity, model capability, evidence
   level, and product alias. A provider-level boolean must not authorize a
   model task.
5. Apply SECRET denial before alias resolution and route construction, and
   preserve it through every state transition.
6. Require each request to carry explicit data class, egress authorization,
   capability, deadline, and one fallback owner; missing security inputs fail
   closed.
7. Keep provider-call retry, provider fallback, and durable job retry as three
   distinct contracts.
8. Keep schema/domain acceptance and prompts in consumers, consistent with
   ADR-001.
9. Treat client HTTP fixtures as requirements until a separately accepted
   server/auth/deployment contract exists.
10. Continue strangler migration with an explicit old path and rollback for
    each consumer; Prozakupki and KMO migrate late.

## 16. Recommended next work package

### Package: governance resolution and draft-stack decomposition

This should be one bounded architecture/governance package, not runtime work.

Entry criteria:

- external architect reviews this report and branch;
- all 101 tests and both read-only guards pass at the reviewed head;
- platform-control owner accepts the package scope;
- PR #3–#5 heads remain pinned or any drift is re-characterized.

Scope:

- record a real platform-control review for the allowed foundation boundary;
- answer questions 1–15 above, or explicitly defer each one;
- decide whether ADR-001 is sufficient or requires a successor;
- confirm the all-form SECRET contract and four-ID allowlist;
- define evidence levels, explicit egress default, route-order authority,
  `UNKNOWN` health, error taxonomy, and deadline semantics;
- produce a reviewed split/rebase plan for PR #3, #4, and #5;
- keep new identities, STT, transports, executor, service, and consumers in
  separate later packages.

What may be changed now: governance documents, decision records, tests, and PR
decomposition plans after explicit authorization. What may not be changed:
production runtime/provider/service code or any consumer.

Exit criteria:

- platform-control contains resolvable review/decision evidence;
- permitted provider IDs and capabilities are machine-readable and unchanged
  unless separately approved;
- every PR logical block has an approved destination;
- a new implementation work package names exact allowed production paths,
  entry tests, rollback, and review gate;
- `ai_core_v0_3_implementation_authorized` remains false unless the authorized
  platform owner explicitly changes it in that governance package.

Only after those exit criteria should a foundation-only implementation package
be considered. Runtime/transports/service remain later work packages.

## 17. Handoff

**Branch:** `test/ai-core-compatibility-characterization-20260909`  
**Production base:** `7569441c18362cfd15524ad73f56f7f35580c86f`  
**Pre-report content head:** `744eed0659aa8e98fb4a37c35692c96831ec7023`  
**Final head:** resolve with `git rev-parse HEAD` after the report commit.  
**Worktree:** `/home/kok4444/projects/ai-core/.worktrees/compatibility-characterization-20260909`

Changed artifacts:

- compatibility tests/helpers under `tests/compatibility/`;
- four fixtures under `tests/fixtures/compatibility/`;
- read-only consumer verifier and changed-path guard under `scripts/`;
- branch-scoped CI history/guard configuration;
- approved baseline/design/plan documents and this report.

Tests/checks:

- full suite twice: `101 passed`, same count/outcome;
- nine pinned consumer contracts verified;
- characterization-only changed paths verified;
- `git diff --check` passed;
- credential/content/network scans produced no unsafe matches;
- PR and governance state refreshed read-only.

Remaining blockers:

- v0.3 implementation remains unauthorized;
- no verifiable platform-control review exists for PR #3–#5;
- SECRET, capability evidence, GPU boundary, route order, UNKNOWN health,
  explicit egress, error taxonomy, deadline enforcement, service ownership,
  identities, and STT decisions remain open as listed in section 13.

Rollback:

- drop the branch, or revert its test/docs/CI commits;
- no production rollback, service restart, provider change, consumer pin
  change, database recovery, deployment lock, release, or tag action is needed;
- user-owned `.worktrees/`, `docs/tmp/`, and `uv.lock` remain recoverable and
  untouched because they were never part of this branch.

Next action: external architect reviews the published branch, then an explicitly
authorized governance-resolution/decomposition package answers the open
questions before any production implementation starts.
