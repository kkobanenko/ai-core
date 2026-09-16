# AI Core C3 v2 — bounded routing design

Date: 2026-09-15

## Status

DESIGN ONLY / NO MERGE AUTHORIZATION

This design replaces the historical C3 implementation with a fresh
contract built on the S1 Foundation and S2A aliases already merged
into the current ai-core main.

Historical donor:

- branch: feat/ai-core-bounded-routing-c3-20260907
- commit: 25c269bb93dd37bd9b1556051972f5e1e60b34ad

Current base:

- main: 1f333206b19634beb17e0d70e4896affa3b31bc1

No historical C3 commit is to be cherry-picked.

## Existing authoritative foundation

S1 already owns:

- exactly four governed provider identities;
- provider identity and network boundary;
- capability evidence;
- privacy and request-egress eligibility.

S2A already owns:

- deterministic legacy provider aliases.

C3 must not weaken or reinterpret those contracts.

## C3 ownership

C3 v2 is a route-planning layer only.

It does not:

- call providers;
- execute retry;
- execute fallback;
- transform payloads;
- sanitize or surrogate data;
- perform network probes;
- create capability evidence;
- turn capability evidence into production authorization;
- own consumer workflow orchestration.

There must remain one explicit fallback owner outside the planner.
Nested fallback remains forbidden.

## Route candidate

A route candidate contains only:

- provider_id
- model

Candidate existence does not grant routing authorization.

## Capability authorization

S1 CapabilityEvidence is evidence only.

C3 must not treat CONFIGURED, UNIT_TESTED, INTEGRATION_TESTED or
RUNTIME_OBSERVED evidence as automatic routing permission.

The caller must explicitly authorize an exact tuple:

- provider_id
- model
- capability

Missing authorization fails closed.

## Route policy

Each planning request must explicitly provide:

- authorized provider IDs;
- exact provider/model/capability authorizations;
- request_egress_authorized boolean.

No authorization is inferred from health, evidence, aliases, model
names, or network location.

## Privacy and egress

C3 resolves the provider through the current S1 provider catalog and
uses the current S1 privacy function is_egress_eligible.

C3 adds no second privacy policy.

Consequences:

- SECRET is always rejected.
- LOCAL_SAME_HOST follows the S1 contract.
- EXTERNAL requires explicit request-level egress authorization.
- UNKNOWN_BOUNDARY requires explicit request-level egress authorization.
- truthy non-boolean authorization must not be accepted.
- C3 does not transform RAW into SANITIZED or SURROGATED data.
- C3 does not prescribe that transformation after route exhaustion.

The historical RawRouteExhaustedError is therefore not part of C3 v2.

## Health

Health is observational state only.

Historical status vocabulary may be retained:

- REACHABLE
- UNREACHABLE
- QUOTA_LIMITED
- AUTH_FAILED
- MODEL_MISSING
- TIMEOUT
- UNKNOWN

Explicit negative observations can remove an otherwise authorized
candidate.

Health must never create provider, capability, privacy, or egress
authorization.

UNKNOWN is absence of a blocking observation, not positive routing
authorization.

Provider-level blocking observations affect all models of that
provider.

Model-level blocking observations affect only the named model.

No network probe belongs in C3.

## Candidate ordering

C3 v2 contains no provider priority, cost, latency, preference score,
or historical priority_hint.

Eligible candidates preserve caller-supplied order.

The planner must not silently reorder candidates.

The first surviving candidate may be exposed as winner, but winner
means only the first candidate in the caller-defined eligible order.

## Rejection reasons

The planner should distinguish at least:

- UNKNOWN_PROVIDER
- UNAUTHORIZED_PROVIDER
- CAPABILITY_NOT_AUTHORIZED
- PRIVACY_EGRESS_DENIED
- HEALTH_BLOCKED

Diagnostics must contain no payload, credentials or secrets.

## Empty route

If require_nonempty is true and no candidate remains, raise one
generic NoEligibleProviderError.

C3 must not infer that the caller should sanitize, surrogate, retry,
switch provider, or otherwise modify the request.

Those decisions belong to the consumer and fallback owner.

## Error taxonomy

The historical dependency-light error classifier is suitable donor
material.

Same-provider retry classification remains narrow:

- timeout
- rate limit

Fallback eligibility metadata may additionally identify:

- connectivity or transport failure
- provider 5xx

Auth, bad request and not-found remain terminal.

Classification is metadata only.
C3 itself performs no retry or fallback.

## Shared deadline budget

The historical AttemptBudget is suitable donor material.

It may:

- receive monotonic timestamps;
- calculate remaining request budget;
- reserve time for possible future attempts;
- bound a configured attempt timeout.

It does not:

- sleep;
- call providers;
- decide fallback ownership.

## Required tests

The implementation must prove:

1. all existing S1/S2A tests stay green;
2. root ai_core public exports stay unchanged;
3. unknown provider fails closed;
4. unauthorized provider is rejected;
5. missing exact capability authorization is rejected;
6. CapabilityEvidence alone cannot authorize a route;
7. SECRET is always rejected;
8. non-local routes require literal request egress authorization;
9. negative health can only remove candidates;
10. UNKNOWN health creates no authorization;
11. caller candidate order is preserved;
12. no hidden provider priority exists;
13. error classification remains dependency-light;
14. deadline budget remains pure;
15. no provider SDK or network dependency is introduced;
16. no provider calls, retry execution or fallback execution exist.

## Explicit exclusions

C3 v2 does not add:

- gpu_whisper
- openai_external
- deepseek_external
- STT_SEGMENTS

Those remain governed separately by platform-control issue #291.

C3 v2 does not modify:

- S1 provider identities;
- S1 capability evidence semantics;
- S1 privacy semantics;
- S2A aliases;
- root ai_core exports;
- dependencies;
- consumer repositories;
- deployment;
- releases or tags.

## Governance

Platform-control issue #292 remains the C3 conformance gate.

Creating and testing a fresh implementation does not authorize merge.

Any implementation must start from the current protected main and
must not merge or cherry-pick the historical stacked PR #5.
