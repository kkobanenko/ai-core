# S1 merge and authoritative closeout — AI Core PR #6

Operator explicitly authorizes merge of **only** AI Core PR #6, and only if the exact reviewed state is still unchanged.

## Pinned reviewed state

- Repository: `kkobanenko/ai-core`
- PR: `#6` — https://github.com/kkobanenko/ai-core/pull/6
- Base branch: `main`
- Required base SHA before merge: `7569441c18362cfd15524ad73f56f7f35580c86f`
- Required head branch: `feat/ai-core-s1-foundation-contracts-20260911`
- Required head SHA: `f73a77706ab88c11ce01066c9b6c92406975da1f`
- Required exact-head hosted CI: run `34572528885` = `success`
- Authoritative platform-control reviewed for S1 start: `main@c78b5e735d9b47e6550f2f6f7df084406c3ecfe0`

External architecture/governance review of this exact PR head is complete and acceptable. Operator has now separately authorized the merge.

## Before merge — mandatory re-verification

Fetch fresh remote truth. Proceed only if **all** are true:

1. PR #6 is still open and mergeable.
2. PR head is exactly `f73a77706ab88c11ce01066c9b6c92406975da1f`.
3. PR base is still `main` and the reviewed base SHA remains exactly `7569441c18362cfd15524ad73f56f7f35580c86f` (no unreviewed base drift/rebase).
4. Exact-head CI run `34572528885` is still successful and no newer required exact-head check contradicts it.
5. No review/comment/change-request has appeared that requires code or governance modification.
6. Changed-file scope is still exactly the reviewed S1 foundation package: pure contracts/tests/docs only; no runtime, transport, service, executor, routing, health, deadline execution, retry/fallback execution, consumer, dependency, lock-file, deployment, release, or tag change.
7. `platform-control/main` still authorizes `S1_foundation_contracts` and still denies runtime/service/transports/executor/consumer migration/new provider IDs/STT/deployment/release/tag.

If any pinned condition differs, **STOP without merge** and report the drift. Do not amend, rebase, cherry-pick, or self-authorize a new reviewed state.

## Authorized action

If every precondition matches:

1. Update PR metadata/checklist only as needed to record:
   - external architecture/governance review complete;
   - exact-head CI green;
   - explicit operator merge authorization recorded in this bridge prompt.
2. Mark the draft PR ready for review only if repository merge procedure requires it.
3. Merge **PR #6 only**, using the repository's normal merge method and an expected-head guard pinned to `f73a77706ab88c11ce01066c9b6c92406975da1f`.
4. Do not delete or rewrite historical branches/tags unless normal repository policy explicitly requires branch cleanup; history rewriting is forbidden.

## Post-merge verification — mandatory

After merge, fetch fresh remote truth and verify:

- PR #6 is `MERGED`;
- record exact merge commit / new `ai-core/main` SHA;
- merged main tree contains the reviewed S1 contracts without merge-only content drift;
- exact root `ai_core.__all__` remains the same nine-symbol contract;
- `pyproject.toml` / dependency boundary is unchanged;
- provider IDs remain exactly:
  - `vm100_local_ollama`
  - `gpu_ollama`
  - `ollama_cloud`
  - `mistral_external`
- `gpu_ollama` remains `UNKNOWN_BOUNDARY`;
- SECRET remains denied for RAW/SANITIZED/SURROGATED across LOCAL_SAME_HOST/EXTERNAL/UNKNOWN_BOUNDARY;
- new provider identities and `STT_SEGMENTS` remain absent;
- no runtime/service/transports/provider calls/executor/routing/health/deadline/retry-fallback execution/consumer migration/deployment/release/tag work occurred;
- PR #3, #4 and #5 remain unchanged;
- consumers remain unchanged.

Run the relevant post-merge S1 tests on authoritative main, including compatibility/root-import isolation and the available characterization/consumer verifier checks. Report exact results.

## Explicitly NOT authorized

This merge authorization does **not** authorize:

- S2 or any next work package;
- aliases or evidence registry implementation;
- route planning, health, normalized error implementation, deadline mechanics;
- provider transports or provider calls;
- runtime/executor/retry/fallback implementation;
- HTTP service/client implementation;
- consumer migration or consumer repository writes;
- new provider identities, `STT_SEGMENTS`, GPU trust promotion;
- infrastructure/deployment, release or tags;
- merge or modification of PR #3–#5.

Do not interpret successful S1 merge as broad `ai_core_v0_3_implementation_authorized`.

## Handoff and stop

After successful merge and verification:

1. Update `docs/agent-bridge/latest-report.md` with exact PR/merge/main SHAs, tests, scope proof, risks, rollback, and current governance state.
2. Archive the detailed closeout report under `docs/agent-bridge/reports/`.
3. Replace `docs/agent-bridge/next-prompt.md` with a **WAIT** prompt stating that S1 is merged/authoritative and that S2 requires a new external review/explicit authorization.
4. Commit/push bridge documentation only.
5. **STOP. Do not start S2 automatically.**

Rollback after merge: separately reviewed revert of the S1 merge commit; never rewrite `main` or existing tags.
