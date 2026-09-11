# S1 merge and authoritative closeout — AI Core PR #6 (drift-tolerant authorization)

> **Historical archive only.** This completed PR #6 authorization is not an
> active prompt or standing authorization for future work packages or
> governance drift. The active source is `../next-prompt.md`.

The operator has explicitly authorized continuation and merge of **only** AI Core PR #6.

## Direct operator authorization

The user explicitly authorized in chat:

> Разрешаю продолжить merge PR #6 при `platform-control/main@52940fd772f948b54b34a5b2c36c6a53ada3f85a`.
>
> Разрешено обновить metadata PR #6, перевести его из draft и слить exact head `f73a77706ab88c11ce01066c9b6c92406975da1f` в `main`.
>
> Последующий drift `platform-control/main` не требует нового подтверждения, если он затрагивает только unrelated operational state (например deployment locks или другие независимые инициативы) и не меняет AI Core governance/S1 authorization.

This direct authorization supersedes the previous bridge rule that required a stop on *any* `platform-control/main` SHA drift. It does **not** relax any AI Core governance or PR-head/base/CI guard.

## Current verified state

- Repository: `kkobanenko/ai-core`
- PR: `#6`
- Base branch: `main`
- Required AI Core base SHA before merge: `7569441c18362cfd15524ad73f56f7f35580c86f`
- Required PR head branch: `feat/ai-core-s1-foundation-contracts-20260911`
- Required exact head SHA: `f73a77706ab88c11ce01066c9b6c92406975da1f`
- Required exact-head CI: run `34572528885` = `success`
- Current observed `platform-control/main`: `52940fd772f948b54b34a5b2c36c6a53ada3f85a`
- Drift from previously reviewed `c78b5e735d9b47e6550f2f6f7df084406c3ecfe0` was verified to affect only `coordination/deployment-lock.yaml` (VM100 lock -> unlocked) and does not change AI Core governance/S1 scope.

## Drift policy for this merge/closeout

Do **not** stop merely because `platform-control/main` advances again.

You may independently inspect and accept further `platform-control/main` drift **without new operator confirmation** when all of the following are true:

1. The drift is unrelated operational/governance activity for another initiative (for example deployment locks, unrelated lifecycle records, unrelated initiative bookkeeping).
2. It does not modify AI Core governance records, ADR-022 semantics, S1 authorization, provider identities, privacy/egress policy, GPU boundary, or merge authorization semantics.
3. It does not revoke or narrow `S1_foundation_contracts` authorization.
4. It does not authorize or require runtime/service/transports/executor/consumer migration beyond S1.

If those conditions hold, record the drift in the closeout report and continue. Do not ask again.

**STOP and request new authorization only if** a material condition changes, including:

- PR #6 head differs from `f73a77706ab88c11ce01066c9b6c92406975da1f`;
- PR #6 base changes or `ai-core/main` no longer equals reviewed base `7569441c18362cfd15524ad73f56f7f35580c86f` before merge;
- exact-head CI is no longer green or a newer required check fails;
- changed-file scope expands beyond the reviewed S1 package;
- a review/change-request appears that requires code/governance changes;
- AI Core governance/S1 authorization changes materially;
- provider set, SECRET/egress rules, GPU boundary, or runtime/service/transports/executor prohibitions change.

Do not stop for unrelated SHA churn alone.

## Mandatory pre-merge verification

Fetch fresh remote truth and verify:

1. PR #6 is still OPEN and MERGEABLE.
2. Head is exactly `f73a77706ab88c11ce01066c9b6c92406975da1f`.
3. Base is still `main@7569441c18362cfd15524ad73f56f7f35580c86f`.
4. Exact-head CI `34572528885` remains successful and no newer required exact-head check contradicts it.
5. Changed files remain the reviewed S1 pure-contract/tests/docs package only.
6. Authoritative platform-control still permits `S1_foundation_contracts` and still denies runtime/service/transports/executor/consumer migration/new providers/STT/deployment/release/tag.

## Authorized action

If the material guards above pass:

1. Update PR #6 metadata/checklist as needed to record external review, green exact-head CI, and explicit operator authorization.
2. Mark PR #6 ready for review if required by repository procedure.
3. Merge **PR #6 only**, using the normal repository merge method and an expected-head guard pinned to `f73a77706ab88c11ce01066c9b6c92406975da1f`.
4. Do not amend/rebase/cherry-pick the reviewed head.
5. Do not rewrite history or tags.

## Mandatory post-merge verification

After merge:

- verify PR #6 is MERGED;
- record exact merge commit and new `ai-core/main` SHA;
- prove merged main tree matches the reviewed S1 content (no merge-only content drift);
- run S1 tests on authoritative main;
- run root-API/import-isolation checks;
- run characterization safety net and pinned consumer verifier where available;
- verify exact nine-symbol root API remains unchanged;
- verify dependencies/`pyproject.toml` unchanged;
- verify provider IDs remain exactly:
  - `vm100_local_ollama`
  - `gpu_ollama`
  - `ollama_cloud`
  - `mistral_external`
- verify `gpu_ollama` remains `UNKNOWN_BOUNDARY`;
- verify SECRET remains denied for RAW/SANITIZED/SURROGATED across LOCAL_SAME_HOST/EXTERNAL/UNKNOWN_BOUNDARY;
- verify no new provider IDs or `STT_SEGMENTS` appeared;
- verify no runtime/service/transports/provider calls/executor/routing/health/deadline/retry-fallback execution/consumer migration/deployment/release/tag work occurred;
- verify PR #3-#5 and consumers remain unchanged.

## Explicitly NOT authorized

This authorization does not authorize:

- S2 or any later work package;
- aliases/evidence registry implementation;
- routing, health, normalized error implementation, deadline mechanics;
- provider transports/calls;
- runtime/executor/retry/fallback;
- HTTP service/client implementation;
- consumer migrations or consumer repository writes;
- new provider identities or `STT_SEGMENTS`;
- GPU trust promotion;
- infrastructure/deployment changes caused by this AI Core work;
- release/tag actions;
- modification/merge of PR #3-#5.

## Handoff and stop

After successful merge and verification:

1. Update `docs/agent-bridge/latest-report.md` with exact PR/merge/main SHAs, test results, scope proof, any accepted unrelated platform-control drift, risks, and rollback.
2. Archive the detailed report under `docs/agent-bridge/reports/`.
3. Replace `docs/agent-bridge/next-prompt.md` with WAIT stating S1 is merged/authoritative and S2 needs new review/authorization.
4. Commit/push bridge documentation only.
5. **STOP. Do not start S2 automatically.**

Rollback after merge: separately reviewed revert of the S1 merge commit; never rewrite `main` or existing tags.
