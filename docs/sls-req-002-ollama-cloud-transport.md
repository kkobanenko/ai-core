# SLS-REQ-002: Ollama Cloud direct-inference transport compatibility

Operator authorized social-listening-service consumption of shared ai-core on 2026-10-08.
This is a **review candidate**, not a shared runtime release or production authorization.
Control-plane review, consumer contract tests, and protected deployment approval remain required.

## Scope

- Keep DEFAULT_CANDIDATES unchanged for every existing consumer.
- Keep canonical provider identities and network classifications unchanged.
- For **ollama_cloud** only: use https://ollama.com/api/chat with Bearer
  OLLAMA_API_KEY, or explicit TransportRequest.api_key in tests/approved callers.
- Fail closed before network on missing egress authorization, missing/invalid API key
  or non-https/non-ollama.com endpoints; redirect following remains forbidden.
- No provider SDK, nested retries, direct product HTTP transport, or global route changes.
- No secret values in source code, report, CI, logs or traces.

## Consumer contract

Consumer must use execute_chat with explicit RouteCandidate ordering and
an explicit RoutePolicy permitting specific provider-model-capability triples.
The cloud model is gpt-oss:20b-cloud and is not added to global capability defaults.

Ollama direct cloud API docs: https://github.com/ollama/ollama/blob/main/docs/api/authentication.mdx

## Verification

tests/test_sls_ollama_cloud_auth.py contains offline transport auth/HTTPS/endpoint
and no-key tests. Full CI and consumer contract tests required before merge.

## Rollback

Disable consumer flags; revert only this feature branch / PR. No schema or
production infrastructure changes.
