# AI Core S2 discovery/design review

Date: 2026-09-11
Status: COMPLETE — recommendation only; no S2 implementation authorized
Scope: read-only discovery, design review, and bridge documentation
Active repository: `ai-core`
Branch: `test/ai-core-compatibility-characterization-20260909`
Discovery base: `1780bb6634288465a0dce33a29406cdad15ff7e2`

## Executive outcome

The recommended next implementation package is **S2A only: a strict,
fail-closed compatibility resolver for five historically used provider aliases**.

Do not combine it with an evidence registry. The resolver is a small pure
foundation contract with a narrow compatibility purpose. A useful evidence
registry requires governance decisions that the accepted S1 types do not answer:
provenance, freshness, revocation, conflicting observations, and snapshot versus
ledger semantics.

This report is decision support. It does not authorize S2A, accept a provider or
capability, promote GPU trust, establish runtime eligibility, or permit any
runtime, service, transport, executor, consumer, deployment, release, or PR #3–#5
change.

## Decision requested from the operator

Question: what is the smallest coherent successor to the merged S1 foundation?

Recommended answer: authorize a separately reviewable **S2A alias-resolution
contract only**, after platform-control first records the actual S1 merge state.

That would permit a future implementation proposal with:

- one pure `provider_aliases` module;
- five exact legacy-to-canonical mappings;
- canonical-ID idempotence;
- explicit unknown and ambiguous failures;
- no root API expansion, dependencies, runtime behavior, or consumer changes.

It would not permit an evidence registry, concrete evidence data, new identities,
new capabilities, STT, routing, health checks, fallback, service work, or adoption
by consumers.

## Authoritative state rebaseline

### AI Core S1

The reviewed S1 commit and the current `ai-core/main` tree remain identical.

| Item | Verified value |
|---|---|
| S1 reviewed base | `7569441c18362cfd15524ad73f56f7f35580c86f` |
| S1 reviewed head | `f73a77706ab88c11ce01066c9b6c92406975da1f` |
| S1 merge / `ai-core/main` | `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e` |
| Reviewed and merged tree | `56693cca4419407feb5340e6ee421e37e798eb7c` |
| Hosted main CI | run `34603741364`, success |
| Root public API | unchanged, exact nine-symbol contract |

S1 accepts exactly these provider identities:

- `vm100_local_ollama`;
- `gpu_ollama`;
- `ollama_cloud`;
- `mistral_external`.

`gpu_ollama` remains `UNKNOWN_BOUNDARY`. Endpoint normalization and reachability
were confirmed previously. The HTTP 503 GPU vision attempt remains
`FAILED_INCONCLUSIVE`; it is not runtime capability proof and must not increase
the model's evidence level.

S1 accepts exactly these capabilities:

- `text`;
- `structured_json`;
- `vision_image`;
- `ocr_pdf`.

`STT_SEGMENTS` is absent and remains unaccepted.

S1 accepts exactly these evidence labels:

- `CONFIGURED`;
- `UNIT_TESTED`;
- `INTEGRATION_TESTED`;
- `RUNTIME_OBSERVED`;
- `FAILED_INCONCLUSIVE`.

Capability evidence is keyed by provider, model, capability, and boundary.
`RUNTIME_OBSERVED` is an observation, never an eligibility or routing decision.

S1 privacy behavior remains fail-closed:

- `SECRET` is denied for every outbound form and boundary;
- absent request authorization denies external and unknown boundaries;
- alias resolution must never weaken or precede future privacy authorization.

### Verification performed for this review

| Check | Result |
|---|---|
| `PYTHONPATH=src python3.10 -m pytest -q` against S1 source | 71 passed; 2 known non-functional warnings |
| Compatibility characterization against S1 source | 77 passed |
| Pinned consumer verifier | 9 verified |
| `origin/main` commit and reviewed tree comparison | exact match confirmed |
| Root import/API and dependency boundary | unchanged; standard-library-only S1 additions |

The warnings were the known pytest-asyncio default-loop-scope warning and the
read-only pytest-cache warning. They do not change the test result.

## Platform-control governance audit

Authoritative platform-control evidence was read from `origin/main`, not from its
dirty local checkout.

| Item | State |
|---|---|
| `platform-control/origin/main` | `52940fd772f948b54b34a5b2c36c6a53ada3f85a` |
| Governing ADR | `ADR-022-ai-core-foundation-governance.md` |
| Broad v0.3 implementation authorization | false |
| Recorded work package | `S1_foundation_contracts` |
| Runtime/service/transports/executor/consumer/release/deploy | not authorized |
| Recorded AI Core main | stale: `7569441c18362cfd15524ad73f56f7f35580c86f` |
| Recorded S1 merge authorization/state | stale: merge not recorded as completed |
| Actual AI Core main | `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e` |

The direct bridge authorization and completed PR #6 merge are real, but the
control plane has not been reconciled to that result. Therefore S2 implementation
must not begin from the current governance record.

Before any S2A implementation, platform-control should:

1. record AI Core main `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e`
   and the completed S1 result while retaining broad implementation=false;
2. authorize the exact S2A-only start boundary, including the five mappings,
   strict matching, unchanged root API, and negative space below;
3. preserve a separate merge gate after implementation review and GREEN CI.

ADR-022 supports pure identity, capability, evidence, and privacy foundation
contracts in principle. It does not itself activate this exact alias package.
A bounded successor decision can likely authorize S2A without a new ADR, provided
it does not change the accepted governance semantics.

## PR #4 donor review

PR #4 was inspected only as historical donor evidence. Its branch, metadata, and
history were not changed.

| Item | Fresh state |
|---|---|
| URL | `https://github.com/kkobanenko/ai-core/pull/4` |
| State | OPEN, DRAFT |
| Mergeability | CLEAN / MERGEABLE |
| CI | success |
| Base | PR #3 branch at `4e26d67b825194e489a6a8b553c2a53dfea2a81f` |
| Head | `1b2569a612968a3ac5099dea955cfccdcb191d52` |
| Review/comments | none observed |

### Concepts worth retaining

- a dedicated `provider_aliases` module;
- canonical IDs resolve idempotently;
- unknown and ambiguous inputs have distinct errors;
- direct alias mappings terminate at canonical identities.

### Content that must be redesigned

- The resolver uses `str(name).strip().lower()`. That silently accepts malformed
  values and broadens the compatibility boundary. S2A should require an exact
  string and fail closed on case, whitespace, empty, and non-string inputs.
- PR #4 labels configured consumer YAML as `CURRENT_OBSERVED`. Configuration is
  only `CONFIGURED`; it is not a runtime observation.
- Its two evidence labels, `HISTORICAL_PROVEN` and `CURRENT_OBSERVED`, conflict
  with the accepted five-level S1 vocabulary.
- The branch is stacked on PR #3 and carries model profiles, endpoints,
  credentials, and transport behavior outside S2A.

### Content explicitly rejected or deferred

- `local_gpu_whisper -> gpu_whisper`;
- `openai -> openai_external`;
- `deepseek -> deepseek_external`;
- provider IDs `gpu_whisper`, `openai_external`, `deepseek_external`;
- `STT_SEGMENTS`;
- concrete model profiles;
- transport, endpoint, credential, route, retry, fallback, or runtime behavior.

PR #4 should not be cherry-picked, rebased, split, or modified as part of this
package. If S2A is authorized, implement the accepted idea afresh from current
`main`.

## Consumer evidence inventory

The pinned nine-consumer characterization remains reproducible. Fresh remote
default-branch tips were also checked so that historical fixtures are not
misrepresented as current state.

| Consumer | Fresh default tip | Relevant S2 finding |
|---|---|---|
| Prozakupki | `039eb08ed03385e5549782c879ed33473c4746dd` | five useful legacy names plus ambiguous/unaccepted names; configuration is not runtime proof |
| KMO | `24d8d8e27f3e6231a547f9de6f7882a6d1c798eb` | `local_gpu_ollama`, `ollama_local`, `mistral`; read-only reference |
| Zoom | `9cc80497baa748937ee7e7e2eb48f80fa398446b` (`master`) | local CPU/GPU legacy names; config unchanged from characterized evidence |
| Clin-rec | `1d16d54bfcd0631388cf29450a1c82ed233968f2` | code/config branches encode provider and fallback assumptions |
| Landing Sell | `37ba801d9fd32c8a6c09837a786abb0f1d26b306` | local `ollama` mapping is deployment-specific and globally ambiguous |
| agent-lab | `c87b3e987f70323355b78ec16858acabe8ef260e` | `agent-worker`/`agent-reviewer` are product model-route aliases, not provider IDs |
| Alpha University | `7216b379518cd4d5e934daeb50bdd5a6cb503d8a` | no current AI provider runtime |
| transcription-service | `067a0f2b9441837a4f1897f19de8707992161128` | service/backend selectors do not authorize STT provider identity or capability |
| image-description-service | `0d6b795af88d09ffd6991679079d1a8377b5d6e8` | service/backend selectors are not provider aliases or capability evidence |

For the first five consumers, current relevant provider/config files matched the
pinned evidence, except for unrelated Landing Sell gateway expansion. Its alias
behavior in `ai/config.py` and `ai/call_ledger.py` was unchanged. No consumer was
modified or imported.

## Alias provenance and classification

### Recommended exact aliases

| Legacy name | Canonical target | Evidence and boundary |
|---|---|---|
| `ollama_local` | `vm100_local_ollama` | Prozakupki, KMO, Zoom, Clin-rec; unambiguous current inventory mapping |
| `local_gpu_ollama` | `gpu_ollama` | Prozakupki, KMO, Zoom, Clin-rec; identity mapping only, no trust promotion |
| `local_gpu_vision` | `gpu_ollama` | Prozakupki uses the same physical GPU Ollama endpoint; does not imply vision capability |
| `mistral` | `mistral_external` | Prozakupki, KMO, Clin-rec, Landing Sell; identity only |
| `mistral_ocr` | `mistral_external` | Prozakupki OCR configuration; does not imply OCR model/capability evidence |

`ollama_cloud` is already canonical and needs no alias.

### Must remain ambiguous

`ollama` must fail with an ambiguity error. It denotes local loopback behavior in
Prozakupki, while Landing Sell maps it locally to a VM100-oriented ledger name.
The physical deployment meaning is contextual and cannot safely be promoted to a
global canonical identity. PR #4 independently treated it as ambiguous.

### Must remain outside the provider-alias table

| Name | Reason |
|---|---|
| `openai`, `deepseek`, `local_gpu_whisper` | would resolve to identities not accepted by S1 |
| `gpu_whisper`, `openai_external`, `deepseek_external` | not accepted canonical identities |
| `fake`, `ai_core` | media-service backend/test selectors, not provider identities |
| `agent-worker`, `agent-reviewer` | agent-lab logical model/route aliases owned by that product |

## Why the evidence registry is not ready

An S2 evidence registry is not a harmless container around the S1 record type.
The following semantics are unresolved:

1. **Provenance and authority.** `CapabilityEvidence` has no source reference,
   observed-at timestamp, revision, or authority class.
2. **Freshness and revocation.** There is no rule for expiry, supersession,
   invalidation, or catalog-boundary changes.
3. **Conflicts.** `FAILED_INCONCLUSIVE` can coexist with another observation and
   is not a lower point on a simple success ladder.
4. **Query meaning.** Returning a maximum/latest level would erase negative or
   conflicting observations. A boolean eligibility query would improperly turn
   evidence into policy.
5. **Durability model.** Snapshot, append-only ledger, and curated registry have
   different ownership and audit guarantees.
6. **Historical validity.** Current constructor validation binds records to the
   current provider boundary, complicating preservation if the catalog changes.
7. **Dataset authority.** No concrete cross-consumer evidence dataset has been
   authorized. Mechanics alone would not remove duplicated consumer declarations.

A later S2B could safely start with immutable snapshots and exact-filter queries,
keeping conflicting records rather than collapsing them. It first needs explicit
governance answers for provenance, conflict, freshness/revocation, and snapshot
versus ledger behavior. It must continue to treat `RUNTIME_OBSERVED` as evidence,
not production eligibility.

## Options considered

| Option | Benefit | Cost/risk | Recommendation |
|---|---|---|---|
| S2A alias resolver only | immediate compatibility value; tiny pure contract; easy rollback | requires exact governance gate | **Recommend** |
| S2B evidence registry only | extends S1 type system | unresolved semantics; no authorized dataset; little immediate compatibility value | Defer |
| Combined aliases + registry | one nominal milestone | weak cohesion, larger review surface, governance ambiguity, harder rollback | Reject now |
| Defer both | no new code risk | leaves five mappings duplicated and delays safe compatibility convergence | Accept only if governance cannot be reconciled |

## Recommended S2A contract

### Proposed future files

- `src/ai_core/provider_aliases.py`
- `tests/test_s2_provider_aliases.py`

Those files are a design proposal only. They were not created in this package.

### Proposed public submodule API

```python
class ProviderAliasError(ValueError): ...
class UnknownProviderAliasError(ProviderAliasError): ...
class AmbiguousProviderAliasError(ProviderAliasError): ...

def get_provider_aliases() -> Mapping[str, str]: ...
def resolve_provider_id(name: str) -> str: ...
```

Contract rules:

- accepted canonical IDs resolve to themselves;
- exactly the five listed aliases resolve to accepted canonical IDs;
- `ollama` raises `AmbiguousProviderAliasError`;
- all other inputs raise `UnknownProviderAliasError` or a documented strict
  type failure;
- matching is exact and case-sensitive;
- no `str()` coercion, whitespace trimming, or lowercase normalization;
- the mapping exposed by `get_provider_aliases()` is immutable;
- every target is a member of current `CANONICAL_PROVIDER_IDS`;
- aliases never target aliases, making cycles structurally impossible;
- several aliases may share one canonical target;
- resolution returns only a canonical identity string.

The module must not grant or infer model, capability, boundary override, egress,
route, health, priority, transport, endpoint, credentials, retry, fallback, or
runtime eligibility.

### Compatibility and packaging boundary

- Keep `ai_core.__all__` unchanged; consumers would use an explicit submodule
  import after a future adoption decision.
- Use only the standard library and accepted S1 contracts.
- Do not change `pyproject.toml`, lock files, extras, import-time provider SDKs,
  or tracing imports.
- Do not edit consumers in S2A.
- Privacy authorization remains a separate fail-closed gate and must precede any
  future provider call. Resolution itself performs no call.

### Explicit negative space

S2A contains no:

- evidence registry or concrete evidence records;
- models or model aliases;
- capability inference or capability promotion;
- provider health or availability;
- endpoint, credential, transport, or network behavior;
- routing, prioritization, retry, or fallback;
- provider-call retry, provider fallback, or durable workflow retry contract;
- service/API/deployment surface;
- consumer migration;
- STT or new provider identities;
- GPU trust or runtime validation change;
- PR #3–#5 modification or integration.

## Future verification plan for an authorized S2A implementation

### Contract tests

- all four accepted canonical IDs are idempotent;
- the five exact aliases resolve as specified;
- returned alias mapping is immutable;
- aliases and canonical IDs do not overlap;
- every target belongs to the accepted four-ID catalog;
- targets are never aliases and cycles cannot form;
- `ollama` raises the ambiguous error;
- unknown and unaccepted names fail closed, including `openai`, `deepseek`,
  `local_gpu_whisper`, `gpu_whisper`, `openai_external`, and
  `deepseek_external`;
- backend/model-route selectors fail closed: `fake`, `ai_core`, `agent-worker`,
  `agent-reviewer`;
- `None`, non-string values, empty strings, whitespace, case variants, leading or
  trailing whitespace all fail; no coercion or normalization occurs.

### Composition tests

- `SECRET` remains denied for every outbound form after any alias resolves;
- `mistral` resolves external, then missing request authorization still denies;
- `local_gpu_vision` resolves unknown-boundary GPU, then missing request
  authorization still denies;
- alias resolution exposes no capability/evidence API and never creates runtime
  evidence;
- `local_gpu_vision` cannot prove `VISION_IMAGE`;
- `mistral_ocr` cannot prove `OCR_PDF`;
- root exports and import isolation remain unchanged;
- no new dependency or packaging change occurs.

### Regression checks

- full unit suite remains green;
- all 77 compatibility characterization tests remain green;
- all nine pinned consumer fixtures remain verified;
- rejected PR #4 provider IDs, STT, models, and transport content do not appear;
- `git diff --check` and hosted CI are green before a separate merge decision.

## Governance questions to resolve

### Required for S2A start

1. May platform-control record the completed S1 merge and current AI Core main
   while preserving broad implementation=false?
2. May S2A include exactly the five mappings in this report and no others?
3. Is exact case-sensitive fail-closed matching accepted, with `ollama` explicitly
   ambiguous?
4. Is the unchanged root API and explicit-submodule-only surface accepted?
5. Will S2A merge remain a separate, exact-head authorization after review?

### Required later for S2B, not for S2A

1. What provenance fields and authorities make evidence admissible?
2. Is evidence stored as an immutable snapshot, append-only ledger, or curated
   registry?
3. How are conflicting and `FAILED_INCONCLUSIVE` observations represented?
4. What are the freshness, expiry, supersession, and revocation rules?
5. How is historical evidence retained across provider-boundary changes?
6. Which exact evidence dataset, if any, becomes authoritative?

No answer to the S2A questions should implicitly answer S2B, authorize runtime,
accept STT/new provider identities, or promote GPU trust.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Alias resolution becomes implicit routing | return only canonical identity; prohibit route/health/priority data |
| Legacy spelling silently expands accepted inputs | exact matching; no coercion, trim, or case folding |
| Alias implies capability | explicit identity-only contract and negative tests |
| Unknown GPU boundary is accidentally promoted | preserve S1 catalog boundary; no boundary override in aliases |
| Privacy checks are bypassed | aliases grant no authorization; future call path must run privacy gate |
| PR #4 imports unaccepted scope | reimplement from current main; never cherry-pick donor branch |
| Evidence becomes eligibility | defer registry; keep evidence and policy separate |
| Governance record diverges from repository | reconcile platform-control before S2A implementation starts |

## Rollback

This package changes bridge documentation only. It has no runtime, dependency,
consumer, deployment, release, or governance-control effect. Rollback is a normal
revert of the documentation commit on the bridge branch. The active prompt must
remain `WAIT` after rollback unless the operator issues a new exact authorization.

## Handoff

| Field | Value |
|---|---|
| Branch | `test/ai-core-compatibility-characterization-20260909` |
| Documentation base | `1780bb6634288465a0dce33a29406cdad15ff7e2` |
| AI Core authoritative main | `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e` |
| Platform-control authoritative main inspected | `52940fd772f948b54b34a5b2c36c6a53ada3f85a` |
| PR #4 donor head inspected | `1b2569a612968a3ac5099dea955cfccdcb191d52` |
| Outcome | recommend S2A only; defer S2B |
| Implementation performed | none |
| Consumer changes | none |
| Next state | `WAIT` for operator/ChatGPT governance review |

Recommended next work package: **platform-control reconciliation and an exact S2A
start-gate decision**, still documentation/governance only. Only after that gate
may a separate branch implement the bounded alias contract and return for an
independent exact-head merge decision.
