# S0 MERGE + CLOSEOUT — explicit operator authorization

Operator explicitly authorizes merge of **platform-control PR #294 only**.

This authorization supersedes the previous WAIT only for the bounded S0 merge/closeout actions below. It does **not** authorize S1 or any runtime/product work.

## Authorized target

- Repository: `kkobanenko/platform-control`
- PR: `#294` — `docs(ai-core): record S0 governance`
- Expected branch: `governance/ai-core-s0-20260910`
- Expected base before merge: `main@6445a2ed8614ae0bb663b92413ebf04f3fbc1d99`
- Expected reviewed head: `0fd1354ee471b40165a50d016a6a28970db8443b`
- Known hosted CI: Infrastructure CI run `34486623033` GREEN on the reviewed head.

External architecture/governance review has been completed by ChatGPT for this exact reviewed S0 content, and the operator has now explicitly stated: **"Разрешаю merge PR #294"**.

## 1. Pre-merge fail-closed verification

Before mutating PR state, refresh GitHub truth and confirm:

- PR #294 is still OPEN and points to the expected head/base;
- head SHA is exactly `0fd1354ee471b40165a50d016a6a28970db8443b`;
- base `platform-control/main` is still exactly `6445a2ed8614ae0bb663b92413ebf04f3fbc1d99`;
- CI for that exact head is GREEN;
- no unexpected commits, review-requested changes, conflicts, or scope expansion appeared;
- diff remains governance/docs/tests only and contains no product/runtime/deployment code.

If any of these assumptions changed materially, **do not merge**. Record the drift in the bridge report and stop for operator/ChatGPT review.

## 2. Merge authorization

If all preconditions remain true, you are explicitly authorized to:

- mark PR #294 ready for review if GitHub requires leaving draft state before merge;
- merge **PR #294 only**, pinned to the exact expected head SHA;
- use the repository's normal safe merge method; do not rewrite unrelated history.

Do not merge PR #3, #4, #5 or any other PR.

## 3. Post-merge verification

After merge, fetch fresh `platform-control/main` and verify that the merged authoritative state contains, consistently across the relevant control-plane files:

- factual `ai_core_main_sha = 7569441c18362cfd15524ad73f56f7f35580c86f`;
- ADR-022 and recorded operator decision;
- `authorization.status = FOUNDATION_ONLY`;
- `foundation_contracts_authorized = true`;
- **`foundation_work_package_start_authorized = false`**;
- runtime implementation = false;
- service implementation = false;
- provider transports = false;
- executor = false;
- consumer migration = false;
- new provider identities = false;
- `STT_SEGMENTS` = false;
- GPU remains `UNKNOWN_BOUNDARY`;
- S1 has not started.

Also verify PR #3–#5 remain unchanged and no deployment/release/tag action occurred.

Run or inspect the narrow S0 governance tests/validator needed to prove the merged `main` is internally consistent. Do not create fixes outside governance/docs/tests if a new failure appears; stop and report instead.

## 4. S0 closeout handoff

Update the AI Core bridge on branch:

`test/ai-core-compatibility-characterization-20260909`

Update:

- `docs/agent-bridge/latest-report.md`;
- archive a closeout report under `docs/agent-bridge/reports/`;
- replace `docs/agent-bridge/next-prompt.md` with a WAIT state after completion.

The closeout report must include:

- PR #294 final state;
- merge SHA;
- new authoritative `platform-control/main` SHA;
- exact post-merge governance flags;
- validation results;
- whether issues #291–#293 changed state;
- confirmation that `ai-core/main`, consumers, PR #3–#5, runtime, service, deployment, releases and tags are unchanged;
- recommended S1 scope, but **do not start S1**.

Push bridge documentation as needed so ChatGPT can read the final report.

## 5. Still forbidden

This authorization does **not** permit:

- S1 foundation source changes;
- any `src/ai_core/**` change;
- runtime, transport, executor or HTTP service implementation;
- consumer changes or migration;
- new provider identities;
- `STT_SEGMENTS`;
- GPU trust promotion;
- deployment, release or tag;
- modification/merge/rebase of AI Core PR #3–#5;
- broadening `ai_core_v0_3_implementation_authorized`.

After successful S0 merge and closeout, return to **WAIT** for a new explicit operator/ChatGPT authorization.
