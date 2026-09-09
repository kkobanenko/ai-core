# Next prompt — review and governance decision packet

Characterization work package accepted.

Use `docs/agent-bridge/latest-report.md` and
`docs/reports/2026-09-09-ai-core-compatibility-characterization-report.md`
as the starting evidence.

Do **not** begin runtime implementation, provider transports, consumer migration, deployment, release, tag, or merge.

## Goal

Complete two bounded activities:

1. create a review/CI surface for the finished characterization package;
2. prepare an operator-ready governance decision packet for the next architectural decisions.

Do not resolve governance decisions on behalf of the operator.

## Part A — characterization draft PR and hosted CI

Current branch:

`test/ai-core-compatibility-characterization-20260909`

Current expected remote HEAD:

`f718034484b8b2af93d78ccdc7d5a240b7a6459e`

First independently verify the branch/head and that `main` remains:

`7569441c18362cfd15524ad73f56f7f35580c86f`

Confirm no production/consumer/platform-control change has appeared.

Create a **DRAFT pull request**:

`test/ai-core-compatibility-characterization-20260909 -> main`

Purpose of this PR is:
- hosted CI;
- code review surface;
- durable characterization evidence.

It is **not** merge authorization.

PR description should clearly state:
- characterization/tests/docs only;
- production `src/ai_core/**` unchanged;
- 101 local tests passed;
- nine consumer contracts verified;
- 38 allowed paths verified;
- no runtime/service/consumer migration;
- runtime implementation remains unauthorized;
- PR #3–#5 remain separate and blocked.

Allow GitHub Actions to run.

Inspect the CI result.

If CI fails:
- investigate;
- fix only characterization/test/CI issues within the existing permitted scope;
- do not modify production source to obtain green CI;
- rerun until the characterization branch is legitimately green or a real environment blocker is proven.

Do not merge the draft PR.

Record:
- PR number;
- reviewed HEAD;
- workflow run;
- result;
- any Python 3.10/3.12 differences.

## Part B — operator governance decision packet

After CI evidence is obtained, prepare:

`docs/agent-bridge/reports/2026-09-09-ai-core-governance-decision-packet.md`

This is a decision-support document, not an accepted ADR.

Use the 15 open questions from the characterization report, but consolidate overlapping questions into a smaller number of coherent decision groups where appropriate.

For each decision provide:

- **Question**
- **Why it matters**
- **Current evidence**
- **Recommended decision**
- **Alternative(s)**
- **Consequences of recommended choice**
- **Consequences of alternatives**
- **What remains deferred**
- **Effect on PR #3 / #4 / #5**
- **Whether explicit operator/platform-control approval is required**

At minimum cover:

### A. Foundation boundary
- whether a new additive canonical foundation is permitted;
- root API remains unchanged;
- contracts live in submodules;
- tracing stays dependency-light.

### B. Privacy / SECRET / egress
- all-form SECRET denial;
- explicit request-level egress authorization;
- missing egress permission must fail closed;
- transformed payload must not bypass SECRET.

### C. Provider identity and GPU boundary
- accepted four current identities;
- unresolved `gpu_ollama` boundary;
- proposed `gpu_whisper`, `openai_external`, `deepseek_external`;
- do not silently accept new identities.

### D. Capability evidence
Define meaningful evidence levels, for example:
- configured;
- unit-tested;
- integration-tested;
- runtime-observed.

Recommend which minimum level may influence routing.

Separate model capability from provider identity.

### E. STT / Vision / OCR
- `STT_SEGMENTS`;
- historical OCR/vision evidence;
- consumer requirements versus canonical acceptance;
- what should stay deferred.

### F. Routing / health
- request order versus global priority;
- deterministic tie-break;
- `UNKNOWN` health eligibility;
- fail-closed versus bounded exploration.

### G. Errors / retry / fallback / deadlines
- canonical error taxonomy;
- provider-call retry;
- provider fallback;
- durable job retry;
- single fallback owner;
- shared end-to-end deadline semantics.

### H. AI Core HTTP service
- whether service is part of the accepted target;
- client vs server ownership;
- auth/credentials;
- payload sanitation;
- deployment ownership;
- whether the existing transcription/image-description HTTP contracts should be adopted, revised, or treated only as consumer evidence.

Do not implement any of these decisions.

## PR #3–#5 decomposition proposal

Based on the recommendations, produce a concrete decomposition table for all logical blocks of PR #3, #4, and #5.

For every block specify one:

- `FOUNDATION_CANDIDATE`
- `FIX_BEFORE_FOUNDATION`
- `SEPARATE_GOVERNED_WP`
- `DEFER_TO_RUNTIME`
- `REJECT_REDESIGN`

Do not rewrite the PR branches yet.

The objective is to make the next implementation package mechanically clear after operator decisions.

## Platform-control

Read current authoritative platform-control evidence read-only.

Do not change platform-control in this package.

Explicitly retain the observed-state drift finding unless current evidence proves it has already been corrected.

Do not treat issues #291–#293 as approvals unless actual approval evidence now exists.

## Agent bridge

When finished:

- update `docs/agent-bridge/latest-report.md`;
- archive the report in `docs/agent-bridge/reports/`;
- leave `docs/agent-bridge/next-prompt.md` in a stopped/waiting state.

The report must include:
- characterization draft PR and CI result;
- current Git SHAs;
- decision packet summary;
- your recommended decisions;
- PR #3–#5 decomposition;
- exact questions requiring operator choice;
- recommended next WP.

Push the working branch/report as needed when explicitly required for the draft PR/review surface.

Do not merge anything.

Stop after producing the decision packet and hand control back to ChatGPT/user.
