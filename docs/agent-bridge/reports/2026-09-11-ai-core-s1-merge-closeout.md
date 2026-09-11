# AI Core S1 merge closeout

**Date:** 2026-09-11
**Result:** PR #6 merged, verified, and stopped at WAIT

## Authorization and preconditions

The operator directly authorized metadata update, draft removal, and merge of
only PR #6 at exact head
`f73a77706ab88c11ce01066c9b6c92406975da1f`. The authorization excluded S2,
runtime, service, transports, consumers, releases/tags, and PR #3-#5.

Immediately before merge:

- PR #6 was `OPEN`, ready, `MERGEABLE`, and `CLEAN`;
- base was exactly `7569441c18362cfd15524ad73f56f7f35580c86f`;
- head was exactly `f73a77706ab88c11ce01066c9b6c92406975da1f`;
- exact-head CI `34572528885` was successful;
- reviews and comments were empty;
- changed paths were exactly the reviewed ten S1 source/test/docs files;
- dependency, lock-file, runtime, consumer, deployment, and release paths were
  absent.

`platform-control/main` had advanced from `c78b5e7...` to
`52940fd772f948b54b34a5b2c36c6a53ada3f85a`. Read-only inspection proved the
net change affected only `coordination/deployment-lock.yaml`; no AI Core S1
governance file changed. The drift was reported and the operator explicitly
instructed continuation against the new SHA.

## Merge result

- PR: https://github.com/kkobanenko/ai-core/pull/6
- State: `MERGED`
- Merge time: `2026-09-11T13:20:22Z`
- Merge commit / new `main`:
  `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e`
- Reviewed PR head:
  `f73a77706ab88c11ce01066c9b6c92406975da1f`
- Both trees:
  `56693cca4419407feb5340e6ee421e37e798eb7c`
- Content diff from reviewed head to merged main: empty.
- Source branch was not deleted or rewritten.

The merge introduced only:

- three pure contract modules;
- four focused test modules;
- S1 design, plan, and project handoff documents.

No pre-existing production file changed.

## Contract proof

- Root API remains the existing exact nine-symbol `ai_core.__all__`.
- Accepted provider IDs remain exactly `vm100_local_ollama`, `gpu_ollama`,
  `ollama_cloud`, and `mistral_external`.
- `gpu_ollama` remains `UNKNOWN_BOUNDARY`.
- Failed/inconclusive evidence is not runtime observation or routing promotion.
- SECRET is denied in every outbound form across all defined boundaries.
- External and unknown egress require literal request authorization.
- `pyproject.toml` and dependency/lock boundaries are unchanged.
- Aliases, concrete profiles, new IDs, and `STT_SEGMENTS` are absent.
- Runtime, service, transport, provider-call, executor, retry/fallback, routing,
  health, and deadline execution are absent.

## Verification evidence

| Check | Result |
|---|---|
| Pre-merge Python 3.10 suite | 71 passed |
| Exact-head hosted CI `34572528885` | success |
| Post-merge Python 3.10 suite | 71 passed |
| Main hosted CI `34603741364` | success |
| Compatibility characterization | 77 passed |
| Pinned consumer fixture verifier | 9 verified |
| Python compile | pass |
| `git diff --check` | pass |
| Reviewed-head/main tree equality | exact |

PR #3-#5 remain open drafts at their prior heads. Existing release tags retain
their prior tag-object and peeled SHAs. Consumers were not written or migrated.
The user's untracked `.worktrees/` and `uv.lock` were not modified or deleted.

## Risks and governance boundary

S1 is a passive foundation contract layer. It does not alter current consumer
behavior or make any provider route production-eligible. GPU runtime capability
remains unconfirmed: endpoint normalization/reachability existed, while the 503
vision attempt remains failed/inconclusive evidence.

Broad AI Core implementation remains unauthorized. Decisions and work for S2,
aliases, evidence storage, routing/health/errors/deadlines, runtime, transport,
retry/fallback, service ownership, consumer migration, new identities,
`STT_SEGMENTS`, infrastructure, deployment, release, and tags remain outside
this closeout.

## Rollback

Use a separately reviewed mainline-parent-1 revert of
`f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e`. Never rewrite `main` or existing
tags.

## Handoff

- Implementation branch: `feat/ai-core-s1-foundation-contracts-20260911`
- Base SHA: `7569441c18362cfd15524ad73f56f7f35580c86f`
- Reviewed head SHA: `f73a77706ab88c11ce01066c9b6c92406975da1f`
- Main/merge SHA: `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e`
- Bridge branch: `test/ai-core-compatibility-characterization-20260909`
- Next state: **WAIT** pending a newly reviewed and explicitly authorized work
  package.
