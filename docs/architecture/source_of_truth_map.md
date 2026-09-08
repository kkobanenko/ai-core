# AI infrastructure source-of-truth map

**Status:** transition map, not implementation authorization

**Evidence:** `current_state_baseline.md`, `cross_project_ai_inventory.md`,
platform-control `origin/main@6445a2ed8614ae0bb663b92413ebf04f3fbc1d99`

## How to read this map

`Temporary authority` identifies what must be preserved during the strangler
migration. `Future owner` records the transition plan's desired end state.
Where that future state extends accepted platform-control ADR-001, it is marked
**proposed** and cannot be implemented until governance authorizes it.

No current consumer implementation is promoted wholesale to canonical status.
The mandatory transformation is:

```text
extract -> compare -> generalize -> contract -> implement
```

## Ownership map

| Concern | Current implementations | Temporary authority during transition | Future owner | Product/service-owned remainder | Governance state |
|---|---|---|---|---|---|
| Root package API | ai-core v0.1/main and divergent v0.2.x roots | exact main v0.1 root plus immutable tag behavior | ai-core compatibility layer | pinned old adapter until each migration completes | compatibility preservation required; expansion decision pending |
| Tracing API | ai-core main/v0.1; variants in v0.2; consumer Phoenix wrappers | ai-core main for v0.1 consumers; each immutable tag for pinned consumers | ai-core | correlation IDs and domain metadata inputs | accepted shared concern; platform-control review required for changes |
| Trace deployment / collector | platform-control and product deployment manifests | current environment-specific manifests | platform-control governance + designated observability operator | project name/correlation context | accepted; any infrastructure action requires deployment lock |
| Safe attributes / IO policy | v0.1 allowlist; v0.2 renamed variant; product wrappers | current pinned API semantics | ai-core | classification of product metadata | accepted shared concern; exact convergence contract pending |
| Provider identity registry | Prozakupki/KMO configs; v0.2.1; PR #3/#4; product aliases | consumer configs plus accepted four-ID matrix | ai-core registry | task/provider preference, not secret values | four IDs accepted; PR #4 additional IDs pending |
| Model registry | product YAML/env/defaults; v0.2.2; PR #3/#4 | consumer records as evidence only | ai-core registry | task-quality preference and acceptance criteria | proposed; each model/capability needs evidence and review |
| Model capabilities | product config/code; v0.2.2; draft capability profiles | actual consumer path/tests; unknown fails closed | ai-core registry/contracts | task requirement | `TEXT`/`STRUCTURED_JSON` foundation plausible; VISION/OCR separate; `STT_SEGMENTS` unaccepted |
| Provider credentials | distributed consumer environment variables/secrets | existing deployments and product secret ownership | AI Core service credentials boundary | product-to-service authorization | service ownership is proposed; no values in Git/registry; deployment governance required |
| Privacy classification | Landing Sell envelope; product-specific or absent elsewhere | accepted platform-control policy plus each enforceable old behavior | ai-core policy for routing eligibility | product supplies data class and performs domain-specific transformation/DLP where assigned | future centralization proposed; SECRET default DROP/BLOCK accepted in matrix |
| Egress authorization | platform policy, product flags/config, network boundaries | current product path and accepted matrix | ai-core policy/service request authorization | task-specific allowed-egress input | proposed; external access must be explicit/fail-closed |
| Payload sanitization/surrogates | Landing Sell and historical v0.2.1 helpers; product code | existing product privacy handoff | boundary requires a separate decision; routing must never pretend it sanitized | classification, domain redaction and DLP evidence unless explicitly reassigned | unresolved; do not move silently |
| Routing eligibility | provider lists in every consumer; v0.2.1; PR #5 | each old consumer path | ai-core decision layer | candidate constraints/preferences | proposed; ordering and unknown-health policy unresolved |
| Health state | consumer probes/errors; v0.2.1; PR #5 in-memory model | existing consumer health behavior | ai-core runtime/service, isolated by provider and model | product SLO/availability reaction | proposed; UNKNOWN eligibility unresolved |
| Retry | Prozakupki/KMO helpers, workers, service queues, SDKs | existing per-consumer behavior | ai-core runtime for provider-call retries | durable job retries remain in product/service queues | full central runtime extends ADR-001; exact budgets require approval |
| Fallback | ai-core v0.2 client or consumer loops, depending on product | exactly one existing owner per request | ai-core runtime after individual migration | product eligibility constraints and old rollback switch | single owner/nested fallback prohibition accepted; forced ownership transfer not authorized |
| Request deadline | per-attempt consumer timeouts; some shared monotonic deadlines; PR #5 math | existing consumer semantics | ai-core runtime for one bounded inference deadline | durable workflow/job deadline and cancellation policy | proposed; composition contract required before executor work |
| Provider transports | v0.2 LangChain factory; direct Ollama/OpenAI/Mistral/faster-whisper clients in products | old implementations | optional ai-core transports or AI Core service | none after accepted migration, except documented product-specific integration | ADR-001 accepts optional helpers; centralized service is proposed |
| Structured errors | consumer-specific exceptions; v0.2 transport error; PR #5 descriptor | current consumer mappings | ai-core contracts/runtime | mapping to domain/job/user outcomes | proposed taxonomy; PR #5 is incomplete relative to transition plan |
| Structured JSON parsing | ai-core v0.2 parses JSON; products validate domain schemas | current pinned parser plus product validation | ai-core may validate generic structural contract | prompts, domain schema, domain validation and acceptance | domain ownership is accepted; canonical schema-validation boundary needs explicit design |
| Image/OCR/STT contracts | Prozakupki media stack, Tesseract Alpha shadow, media-service HTTP clients | existing paths; media services remain default `fake` | later ai-core contracts/runtime/service | normalization, queues, durable state, domain acceptance | deferred; `STT_SEGMENTS` must not be accepted here |
| Thin client / service API | transcription/image clients propose internal endpoints | no current canonical server contract | ai-core client/server, if separately approved | product auth context and workflow | target plan only; implementation unauthorized |
| Prompts | every product | product repositories | products | all | accepted product ownership |
| Domain schemas/terminology | every product | product repositories | products | all | accepted product ownership |
| Domain validation/business decisions | every product | product repositories | products | all | accepted product ownership |
| Queues/durable workflow state | Prozakupki, media services, products | product/service repositories | products/services | all | accepted product ownership |
| Product persistence | product databases/object stores | product/service repositories | products/services | all | accepted product ownership |
| Product authorization | product APIs/services | product/service repositories | products/services | all | accepted product ownership; service-to-service auth needs separate contract |

## Canonical identity boundary

The currently accepted identities describe provider/network execution
boundaries:

| Canonical ID | Boundary | Current status |
|---|---|---|
| `vm100_local_ollama` | local same host | accepted |
| `gpu_ollama` | unknown/private path; sensitive RAW denied | accepted, boundary intentionally unresolved |
| `ollama_cloud` | external cloud | accepted |
| `mistral_external` | external cloud | accepted |

Historical names may be compatibility aliases only when the mapping is
unambiguous. `local_gpu_ollama -> gpu_ollama` and
`mistral -> mistral_external` are candidates for tested adapters. Generic
`ollama` is ambiguous and must fail closed. `local_gpu_vision` requires a
model/task-aware compatibility test even if its network endpoint maps to
`gpu_ollama`.

`gpu_whisper`, `openai_external`, and `deepseek_external` are discovered
provider evidence, not accepted canonical identities. They remain governance
pending. No identity was changed in this work package.

## Migration invariants

1. The exact current root API and tracing semantics remain available.
2. Immutable tags are never moved or rewritten.
3. New contracts live in dependency-light submodules; tracing-only import must
   not acquire LangChain/httpx/provider-SDK requirements.
4. Unknown provider, model, capability, alias, privacy class, or network
   boundary fails closed.
5. `SECRET` is DROP/BLOCK for every provider and outbound form by default.
   Sanitization cannot silently reclassify a secret.
6. Cloud-forbidden plus local-unavailable returns a policy/no-route error; it
   never falls through to cloud.
7. One runtime request has one fallback owner. Provider transports never hide
   another provider chain.
8. Provider-call retry/fallback share one bounded request deadline. Durable job
   retries remain separate product/service workflow behavior.
9. A compatibility adapter preserves the old observable contract until that
   consumer passes OLD/SHADOW/NEW, acceptance, canary, soak, and rollback gates.
10. Product prompts, domain schemas, domain validation, business rules,
    authorization, queues, persistence, and durable state do not move into
    ai-core.
11. No client endpoint is considered canonical until both client and server
    contracts, auth, errors, deadline, privacy, and deployment ownership are
    approved and tested.

## Open ownership decisions

These are blockers, not decisions made by this map:

- whether the transition plan's centralized runtime/service supersedes the
  currently accepted ADR-001 option-2 library boundary;
- whether payload sanitization/DLP belongs centrally or remains a pre-routing
  consumer responsibility;
- whether unobserved (`UNKNOWN`) provider/model health is eligible;
- whether deterministic route order follows caller preference, canonical cost
  priority, or a policy-specific composition;
- whether request-level allowed egress must always be explicit and how local
  defaults are represented;
- exact canonical error names and mappings;
- additional provider identities and all media capabilities, especially
  `STT_SEGMENTS`;
- service-to-service authentication and deployment/credential ownership for
  the proposed AI Core service;
- an additive root compatibility strategy for historical v0.2 consumers.

Until platform-control records these decisions, temporary authorities remain
the existing consumer paths and immutable pins described in the inventory.
