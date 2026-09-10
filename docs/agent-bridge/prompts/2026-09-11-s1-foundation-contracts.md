# S1 foundation contracts — operator authorization with control-plane gate

The operator explicitly authorizes starting the **S1_foundation_contracts** work package.

This authorization is intentionally narrow. It authorizes only the minimal dependency-light AI Core foundation contracts described by authoritative `platform-control` governance after S0. It does **not** authorize runtime, provider calls, service, transports, executor, consumer migration, release, tag, deployment, infrastructure changes, new provider identities, or `STT_SEGMENTS`.

## 0. Mandatory preflight

First refresh remote truth for both repositories.

Expected authoritative state at authorization time:

- `platform-control/main`: `35a922ceacb51ff2e8e8ccacc00291fbd2155b52` or a later descendant that preserves ADR-022 and the S0 policy;
- `ai-core/main`: `7569441c18362cfd15524ad73f56f7f35580c86f` unless a later main is observed and independently reconciled;
- authoritative policy: `FOUNDATION_ONLY`;
- `foundation_contracts_authorized: true`;
- at the moment of this prompt, `foundation_work_package_start_authorized: false`;
- runtime/service/transports/executor/consumer migration/new providers/STT remain unauthorized.

Read authoritative:

- `platform-control/docs/adr/ADR-022-ai-core-foundation-governance.md`;
- `platform-control/docs/decisions/2026-09-10-accept-ai-core-foundation-governance.md`;
- `platform-control/coordination/initiatives/ai-core-v0.3-design/evidence/operator-decision-ai-core-foundation-governance.yaml`;
- `platform-control/coordination/initiatives/ai-core-v0.3-design/initiative.yaml`;
- `ai-core/docs/governance/2026-09-09-ai-core-decision-packets.md` from the characterization branch;
- `ai-core/docs/governance/2026-09-09-ai-core-pr-decomposition-plan.md` from the characterization branch;
- `ai-core/docs/agent-bridge/latest-report.md`.

If authoritative remote state materially contradicts this prompt, stop and report instead of guessing.

## 1. Control-plane start gate

The operator authorization in this prompt supersedes the previous `WAIT` instruction **only for starting S1 foundation contracts**.

However, do not silently bypass the authoritative control-plane flag.

If `platform-control/main` still has:

`foundation_work_package_start_authorized: false`

then first create a minimal S1-start governance update in `platform-control`.

Permitted platform-control work for this gate:

- governance/config/coordination/docs/tests only;
- record this explicit operator authorization for `S1_foundation_contracts`;
- set the start authorization narrowly for this exact work package;
- preserve `FOUNDATION_ONLY`;
- preserve all runtime/service/transports/executor/consumer/release/tag/deployment/new-provider/STT prohibitions;
- add/update machine guards so a generic implementation authorization cannot be inferred;
- keep AI Core canonical main pointer accurate;
- use a fresh isolated branch/worktree, suggested branch name `governance/ai-core-s1-start-20260911`;
- push the branch and create a **draft platform-control PR** for review.

Do **not** merge that PR without a new explicit operator merge authorization.

If this control-plane update is required, stop after publishing the draft PR and hand control back. **Do not begin AI Core source changes until the S1-start authorization is authoritative on `platform-control/main`.**

If a freshly verified `platform-control/main` already records this exact S1 start authorization, proceed to section 2.

## 2. S1 implementation scope — only after the start gate is authoritative

Create a fresh isolated `ai-core` worktree/branch from freshly verified `ai-core/main`.

Suggested branch:

`feat/ai-core-s1-foundation-contracts-20260911`

Do not base S1 on PR #3/#4/#5 heads. Treat those PRs as evidence/donor material only. Do not rebase, rewrite, close, retarget, or mutate them.

### Allowed production changes

Only dependency-light, pure foundation contracts under explicit `ai_core` submodules, plus focused tests/docs needed to review those contracts.

The intended minimal S1 content is:

1. **Provider identity contracts**
   - exactly the four accepted canonical IDs:
     - `vm100_local_ollama`
     - `gpu_ollama`
     - `ollama_cloud`
     - `mistral_external`
   - fail-closed lookup for unknown identity;
   - identity/security metadata only where supported by ADR-022;
   - `gpu_ollama` remains `UNKNOWN_BOUNDARY`.

2. **Capability/evidence contracts**
   - dependency-light vocabulary/types for model-scoped capability evidence;
   - evidence subject remains `(provider identity, model, capability, network boundary)`;
   - evidence language preserves:
     - `CONFIGURED`
     - `UNIT_TESTED`
     - `INTEGRATION_TESTED`
     - `RUNTIME_OBSERVED`
     - `FAILED_INCONCLUSIVE`
   - `FAILED_INCONCLUSIVE` must never behave as an evidence promotion;
   - do not claim runtime support from configuration/reachability alone;
   - do not add `STT_SEGMENTS`;
   - any vision/OCR vocabulary carried forward must remain pure contract vocabulary and must not create an automatic route or runtime capability claim.

3. **Privacy / egress contracts**
   - `SECRET` denied for `RAW`, `SANITIZED`, and `SURROGATED`;
   - denial applies across local-same-host, external, and unknown boundaries;
   - denial is pre-routing and cannot be weakened by transformation;
   - missing request-level egress authorization fails closed for external and unknown-boundary egress;
   - catalog membership alone never grants egress;
   - fallback authorization is not implemented here, but any pure contract must preserve the invariant that later fallback may only use request-authorized candidates.

4. **Compatibility boundary**
   - exact current nine-symbol root `ai_core.__all__` remains unchanged;
   - current tracing imports and behavior remain compatible;
   - tracing stays dependency-light;
   - all new APIs are explicit submodule APIs unless separately approved later.

### Explicit exclusions from S1

Do **not** implement or add:

- provider SDKs;
- `httpx`, LangChain, OpenAI/Mistral/Ollama SDK dependencies for the new foundation;
- network calls, sockets, HTTP requests, live provider probes;
- endpoint resolution or credential loading as executable runtime behavior;
- credentials/secrets;
- aliases (leave accepted-ID alias work to S2);
- route planner or canonical route selection implementation;
- health probes or automatic health state routing;
- provider-call retry loops;
- provider fallback executor;
- durable workflow retry;
- error taxonomy implementation beyond what is strictly necessary for pure fail-closed foundation lookups;
- deadline/budget executor behavior;
- HTTP service/client/server;
- consumer changes or migrations;
- `gpu_whisper`, `openai_external`, `deepseek_external`, or any other new provider identity;
- `STT_SEGMENTS`;
- GPU trust promotion;
- runtime capability promotion from the historical GPU HTTP 503;
- release, tag, deployment, infrastructure changes.

## 3. Reuse policy for draft PR #3

PR #3 may be read and selectively reused only at the level of individually reviewed logical blocks.

Do not merge/cherry-pick the PR wholesale.

Expected disposition:

- root compatibility and dependency-light type ideas: candidate;
- accepted four-ID constants/types: candidate;
- privacy types: candidate after correction;
- transformed-SECRET eligibility: reject/redesign;
- catalog-only egress authority: reject/redesign;
- endpoint/credential runtime resolution: exclude from S1;
- concrete model profiles: exclude unless they can be represented strictly as non-routing evidence records without unsupported claims; prefer omitting them from the minimal S1 slice;
- aliases: defer to S2;
- routing/health/deadline/executor: defer.

If copying code, preserve provenance in the handoff and explain which logical blocks were reused and how their semantics changed.

## 4. Required tests and validation

At minimum prove:

- exact root `ai_core.__all__` compatibility;
- current tracing import does not require new inference/provider dependencies;
- accepted provider IDs are exactly the four governed IDs;
- unknown provider identity fails closed;
- `gpu_ollama` boundary remains unknown;
- full `SECRET` matrix: 3 outbound forms × all governed network boundaries => denied;
- transformation cannot silently reclassify `SECRET`;
- missing egress authorization denies external/unknown boundary eligibility;
- evidence levels preserve configured/unit/integration/runtime distinction;
- failed/inconclusive does not promote capability;
- no new provider IDs or STT appear;
- no credentials/secrets are introduced;
- existing AI Core behavior remains unchanged outside the new submodules.

Run the repository's supported Python test matrix, including Python 3.10 and 3.12 where CI supports them.

Also use the existing characterization branch/safety-net as read-only external compatibility evidence where practical. Do not weaken or rewrite characterization expectations merely to make S1 pass.

Run consumer fixture verification against the nine pinned consumer contracts where available. A consumer does not need to import the new foundation yet; the purpose is to prove that S1 has not broken current requirements.

Run `git diff --check` and a changed-path/scope audit proving the diff contains only S1 foundation source/tests/docs/CI changes that are genuinely necessary.

## 5. Review surface

After local validation:

- commit the S1 branch;
- push it;
- create a **DRAFT ai-core PR to `main`**;
- do not merge;
- let hosted CI run;
- inspect exact-head CI;
- if CI fails, fix only within S1 scope;
- do not change consumers or runtime code to obtain green CI.

The draft PR description must state clearly:

- S1 is foundation-contracts only;
- authoritative governance source is platform-control ADR-022/S1-start record;
- exact base/head SHAs;
- exact nine-symbol root API unchanged;
- no runtime/network/provider calls;
- no service/transports/executor/consumer migration;
- four provider IDs only;
- all-form SECRET denial and fail-closed egress;
- no aliases/STT/new provider IDs;
- tests and compatibility evidence;
- rollback = close/drop S1 branch before merge.

## 6. Handoff and stop condition

When the current authorized step is complete, update:

- `docs/agent-bridge/latest-report.md`;
- archive the detailed report under `docs/agent-bridge/reports/`;
- set `docs/agent-bridge/next-prompt.md` back to `WAIT`.

If only the control-plane S1-start draft PR was needed, report that and stop before AI Core source work.

If the start gate was already authoritative and S1 implementation proceeded, report:

- platform-control authoritative SHA and exact S1 authorization evidence;
- AI Core base/head;
- changed source/tests/docs;
- which PR #3 blocks were reused versus redesigned/excluded;
- local and hosted test results;
- nine-consumer verification status;
- draft PR number/state/head;
- risks/blockers;
- rollback;
- explicit confirmation that runtime/service/transports/executor/consumers/release/tag/deploy remain untouched.

Do not merge S1. Return control to ChatGPT/operator for review and separate merge authorization.
