# Authorized — merge platform-control PR #295 and verify S1-start gate

Operator explicitly authorizes merge of platform-control PR #295 only.

This authorization supersedes the previous WAIT state only for the bounded merge/closeout actions below. It does **not** authorize AI Core S1 source implementation before the gate is authoritative, and it does **not** authorize merge of any future AI Core S1 PR.

## Preconditions — verify again immediately before merge

Repository: `kkobanenko/platform-control`

Expected PR:
- PR #295
- base branch: `main`
- expected base SHA: `35a922ceacb51ff2e8e8ccacc00291fbd2155b52`
- head branch: `governance/ai-core-s1-start-20260911`
- expected head SHA: `44d30f1a81fe7736c83a6f49ce7fde5c91412b08`
- exact-head Infrastructure CI run `34532744201`: SUCCESS

Before merge, independently re-read remote truth and confirm:
- PR is still open and contains no unexpected commit/diff drift;
- reviewed head is still exactly `44d30f1a81fe7736c83a6f49ce7fde5c91412b08`;
- target main is still compatible with the reviewed base and no conflicting governance change appeared;
- exact-head hosted CI is green;
- no review requests changes;
- changed files remain governance/docs/tests only;
- runtime/service/transports/executor/provider calls/consumers/deployment/release/tag/AI Core PR #3–#5 remain untouched.

If any precondition no longer matches, **do not merge**. Stop and report the drift.

## Authorized merge action

If all preconditions match:
1. update PR #295 review/merge checklist or metadata to reflect the already completed external architecture/governance review, exact-head green CI, and this explicit operator merge authorization;
2. mark ready for review if required by repository process;
3. merge **only PR #295**, pinned to expected head `44d30f1a81fe7736c83a6f49ce7fde5c91412b08`, using the repository's normal merge method;
4. do not rewrite history and do not merge any AI Core PR.

## Post-merge verification

After merge, fetch fresh `platform-control/main` and prove that the reviewed S1-start gate is authoritative without merge-only drift.

Verify at minimum:
- PR #295 is MERGED;
- exact merge/main SHA and tree are recorded;
- `authorized_work_package: S1_foundation_contracts`;
- `foundation_contracts_authorized: true`;
- `foundation_work_package_start_authorized: true`;
- broad `ai_core_v0_3_implementation_authorized: false` remains false;
- runtime/service/provider transports/executor/consumer migration/release/tag/deployment remain false;
- accepted provider IDs remain exactly:
  - `vm100_local_ollama`
  - `gpu_ollama`
  - `ollama_cloud`
  - `mistral_external`
- new provider IDs and `STT_SEGMENTS` remain unauthorized;
- `gpu_ollama` remains `UNKNOWN_BOUNDARY`;
- AI Core main remains `7569441c18362cfd15524ad73f56f7f35580c86f`;
- AI Core PR #3–#5 remain unchanged;
- consumers, runtime, deployment, releases and tags remain unchanged.

Run the narrow S0/S1 governance tests and the normal control-plane validator. Preserve known `/home`↔`/mnt` path-alias baseline findings as baseline rather than hiding them.

## Important: what this merge unlocks

Once the post-merge checks prove the gate authoritative, the previously operator-authorized `S1_foundation_contracts` work package may start in a **fresh AI Core branch from verified `ai-core/main@7569441c18362cfd15524ad73f56f7f35580c86f`**.

However, this merge-closeout task itself should **not yet implement S1 source code**. Close the governance gate first, update the bridge, and hand control back so ChatGPT/operator can verify authoritative state before source work begins.

Still forbidden:
- runtime implementation;
- service implementation;
- transports/provider calls;
- executor or retry/fallback execution;
- consumer changes/migration;
- aliases/routing/deadline/health implementation outside the already authorized S1 boundary;
- new provider identities or `STT_SEGMENTS`;
- GPU trust promotion;
- deployment/infrastructure/release/tag;
- merge of a future AI Core S1 PR.

## Handoff

When complete:
- update `docs/agent-bridge/latest-report.md` with exact PR state, reviewed head, merge SHA, authoritative platform-control main SHA, tests, validator result, unchanged-scope checks, risks and rollback;
- archive the closeout report under `docs/agent-bridge/reports/`;
- return `docs/agent-bridge/next-prompt.md` to WAIT;
- push bridge documentation changes;
- stop and hand control back.

Rollback after merge: only by a separately reviewed revert of the platform-control merge commit; never rewrite main.