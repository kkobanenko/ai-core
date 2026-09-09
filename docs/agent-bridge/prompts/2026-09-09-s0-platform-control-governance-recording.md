# S0 — record accepted AI Core governance decisions

The operator has accepted D1–D6 with the ChatGPT refinements for D4 and D5. The authoritative executable instruction for this iteration is the contemporaneous `docs/agent-bridge/next-prompt.md` written for S0.

Scope summary:

- record accepted D1–D6 through platform-control governance;
- reconcile stale `ai_core_main_sha` observed pointer to freshly verified factual ai-core main;
- preserve narrow foundation-only authorization and keep runtime/service/consumer migration unauthorized;
- D4 refinement: long-term canonical route ordering belongs to AI Core policy; caller-provided ordered candidates are migration/compatibility mode only; UNKNOWN health is fail-closed; AI Core future execution owns provider-call retry/fallback while consumer owns durable workflow retry;
- D5 refinement: accept normalized errors and one end-to-end deadline, but do not freeze the exact enum; preserve machine-distinguishable privacy, egress, no-route, capability, model/provider availability, auth, rate, transport, deadline, malformed-output, schema/contract, invalid-request and unknown-terminal meanings;
- keep exactly four accepted provider IDs;
- new IDs and `STT_SEGMENTS` remain deferred;
- GPU boundary remains UNKNOWN;
- HTTP service remains outside foundation and requires a separate later ADR/design;
- platform-control governance branch/draft review surface allowed; no merge without separate user authorization;
- no ai-core runtime/PR #3–#5/consumer/release/tag/deployment changes;
- hand off through `docs/agent-bridge/latest-report.md` and return `next-prompt.md` to WAIT when complete.

For full requirements, read the S0 `docs/agent-bridge/next-prompt.md` revision associated with this archive commit.