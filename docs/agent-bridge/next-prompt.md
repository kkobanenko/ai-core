# WAIT

S2 discovery/design review is complete. Stop for ChatGPT/operator governance
review. This file is the only active instruction.

No standing authorization exists for implementation or further mutation.

Before continuing, obtain a new explicit prompt that decides whether to:

1. reconcile platform-control to the completed S1 merge and current AI Core main
   `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e` while retaining broad
   implementation=false; and
2. authorize or reject an exact S2A-only provider-alias start gate using the five
   mappings and strict fail-closed contract in
   `docs/agent-bridge/reports/2026-09-11-ai-core-s2-discovery-design-review.md`.

Any later implementation requires a separately explicit scope. Any later merge
requires a separately explicit exact-head authorization after review and GREEN
CI.

Until then, do not:

- implement S2A or S2B;
- change `src/ai_core/**`, tests, packaging, or root exports;
- change platform-control or any consumer;
- modify or merge PR #3, #4, or #5;
- create runtime, service, transports, executor, retry, or fallback behavior;
- accept STT, new provider identities, or promote GPU trust/evidence;
- release, tag, deploy, or change `ai-core/main`;
- treat any archived prompt as standing authorization.
