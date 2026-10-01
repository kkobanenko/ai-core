---
coord_version: 1
state: EXECUTOR_READY
prompt_id: AI-SEMANTIC-JUDGMENT-J1-CONTRACT-01-R1
target_repo: kkobanenko/ai-core
target_branch: feat/semantic-judgment-j1-contract
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/feat-semantic-judgment-j1-contract
base_sha: a9548797c420b2a9d8b158b97a4cd48306c544db
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: src/ai_core/judgment_contracts.py,src/ai_core/judgment_validation.py,src/ai_core/judgment_errors.py,src/ai_core/judgment_runtime.py,src/ai_core/judgment_privacy.py,src/ai_core/judgment_telemetry.py,src/ai_core/judgment_mock.py,tests/test_judgment_contracts.py,tests/test_judgment_validation.py,tests/test_judgment_privacy.py,tests/test_judgment_runtime.py,tests/test_judgment_telemetry.py,tests/test_judgment_fail_closed.py,specs/003-judgment-provider/spec.md,specs/003-judgment-provider/plan.md,specs/003-judgment-provider/tasks.md
required_paths: src/ai_core/judgment_contracts.py,src/ai_core/judgment_validation.py,src/ai_core/judgment_errors.py,src/ai_core/judgment_runtime.py,src/ai_core/judgment_privacy.py,src/ai_core/judgment_telemetry.py,src/ai_core/judgment_mock.py,tests/test_judgment_contracts.py,tests/test_judgment_validation.py,tests/test_judgment_privacy.py,tests/test_judgment_runtime.py,tests/test_judgment_telemetry.py,tests/test_judgment_fail_closed.py
publication_commit: true
publication_push: true
commit_message: feat(judgment): implement corrected J1 provider-neutral contract
transient_paths: uv.lock
---

# AI-SEMANTIC-JUDGMENT-J1-CONTRACT-01-R1

Executor: Local Coordinator + Headless Cursor CLI.
Repository: kkobanenko/ai-core.

Authorized exact base:

a9548797c420b2a9d8b158b97a4cd48306c544db

Target branch:

feat/semantic-judgment-j1-contract

Governance:
- platform-control PR #365 merged;
- post-365 HANDOFF reconciliation PR #366 merged;
- Factory freshness verified:
  HANDOFF_FRESH_WITH_NEWER_UNRELATED_MAIN;
- continuation_allowed=true;
- AUTHORIZE_J1_CONTRACT_ONLY;
- scope=contract_only;
- ADR-023 Accepted;
- G0 CLOSED;
- G1 CLOSED;
- G2/J1 OPEN;
- J2=false.

The previous bridge/package
coord/bridge/ai-semantic-judgment-j1-contract-01
is historical and terminal EXECUTOR_FAILED before repository mutation.
Do not reuse or mutate it.

The corrected platform-control R1 contract supersedes stale historical
Noul-as-neutral wording in the existing ai-core specs.

Read first:
- AGENTS.md
- specs/003-judgment-provider/spec.md
- specs/003-judgment-provider/plan.md
- specs/003-judgment-provider/tasks.md

If those specs conflict with the corrected requirements below, update ONLY
those three spec files to align them. Do not preserve obsolete semantics merely
for compatibility with stale PLAN_ONLY text.

GOAL

Implement only the provider-neutral Semantic Judgment J1 contract.

Required implementation modules:
- src/ai_core/judgment_contracts.py
- src/ai_core/judgment_validation.py
- src/ai_core/judgment_errors.py
- src/ai_core/judgment_runtime.py
- src/ai_core/judgment_privacy.py
- src/ai_core/judgment_telemetry.py
- src/ai_core/judgment_mock.py

Required tests:
- tests/test_judgment_contracts.py
- tests/test_judgment_validation.py
- tests/test_judgment_privacy.py
- tests/test_judgment_runtime.py
- tests/test_judgment_telemetry.py
- tests/test_judgment_fail_closed.py

============================================================
1. PROVIDER-NEUTRAL QUESTION / ANSWER MODEL
============================================================

Implement provider-neutral types:

JudgmentQuestion =
    BinaryQuestion
  | ChoiceQuestion
  | ScoreQuestion

JudgmentAnswer =
    BinaryAnswer
  | ChoiceAnswer
  | ScoreAnswer

Do NOT expose the provider-specific term "Noul" as a provider-neutral ai-core
domain type.

Future adapter mapping only:

TypeSafe/Jev Noul <-> ai-core BinaryQuestion / BinaryAnswer

Do NOT implement the adapter in J1.

BinaryAnswer:
- probability_true: finite float in [0, 1]
- never auto-convert probability to bool
- threshold/business interpretation belongs to consumer

ChoiceAnswer:
- selected choice must be one of declared choices
- confidence finite in [0,1]
- probabilities for exactly all declared choices
- each probability finite in [0,1]
- distribution sums approximately to 1 using an explicit small tolerance

ScoreAnswer:
- expected score must be finite and within declared score/level bounds
- confidence finite in [0,1]
- probabilities by exactly all declared levels
- each probability finite in [0,1]
- distribution sums approximately to 1

Do NOT invent a universal provider-neutral Indeterminate answer.

Uncertainty is represented by probabilities/confidence or normalized execution
errors. A consumer decision pack may itself declare an
INSUFFICIENT_INFORMATION choice if needed.

============================================================
2. BATCH-FIRST REQUEST / RESPONSE
============================================================

A JudgmentRequest represents:
- request_id
- exact decision_pack id/version
- shared state
- named questions: mapping question_name -> JudgmentQuestion
- exact provider/model/version pin
- existing/reused ai-core data classification where applicable
- explicit egress authorization/policy input
- one common total deadline

Requirements:
- question names non-empty
- at least one question
- question names unique by mapping construction
- shared state must be validated according to the contract without introducing
  provider-specific payload types
- exact provider/model/version pins required
- reject wildcards and latest-style aliases for judgment pins

A successful JudgmentResponse represents:
- answers mapping
- exact provider/model/version metadata
- execution metadata allowed by contract

For a successful response:
- every requested question has exactly one answer
- no extra answers
- answer variant must match question variant
- provider free-form/raw text must never cross into consumer-visible contract

Execution failure is represented through normalized judgment error semantics,
not by fabricating partial business answers.

============================================================
3. NORMALIZED ERRORS
============================================================

Canonical categories:

invalid_request
privacy_egress_denied
deadline_exhausted
rate_limited
authentication_failed
provider_unavailable
transport_failed
invalid_provider_response
internal_error

Keep errors typed/deterministic.

Do not leak provider raw payloads, prompts, credentials, stack dumps, or other
sensitive provider output through public error fields.

============================================================
4. PRIVACY / EGRESS
============================================================

Implement only the provider-neutral policy boundary.

No real network calls.

Evaluate privacy/egress before provider invocation.

Reuse existing ai-core privacy/data classification concepts where available;
do not create a competing general privacy model.

Future hosted judgment is allowed only where canonical policy permits it,
including SYNTHETIC / PUBLIC_NO_PII with required explicit egress authorization.

Private/client-sensitive, secret, unknown or otherwise disallowed classes must
fail closed for hosted egress.

Local/no-egress execution must be represented explicitly.

Do not implement provider credentials or SDK handling.

============================================================
5. DEADLINE / RUNTIME CONTRACT
============================================================

Use one total monotonic deadline for a request.

Do not create an independent full timeout per question.

There must be one clear retry/fallback ownership boundary.

J1 provides contract/runtime behavior sufficient for deterministic mock
execution only.

Do NOT integrate with current text routing, provider catalog, transports or
production executor.

============================================================
6. TELEMETRY
============================================================

Metadata only.

Permitted examples:
- outcome/error category
- latency
- retry count
- exact provider/model/version
- decision_pack id/version

Forbidden telemetry:
- shared state payload
- question text/instructions
- prompt
- raw provider response
- answer choice value
- score value
- probability values if they reveal semantic output
- credentials/secrets

============================================================
7. MOCK
============================================================

Implement deterministic in-memory mock_judgment for unit/contract/policy tests.

No HTTP.
No SDK.
No credentials.
No hidden network fallback.

Mock behavior must allow deterministic testing of:
- Binary
- Choice
- Score
- normalized errors
- deadline exhaustion
- privacy/egress denial
- invalid provider response / validation failure

============================================================
8. OWNERSHIP BOUNDARY
============================================================

ai-core owns:
- typed protocol
- validation
- privacy/egress boundary
- total deadline
- normalized errors
- provider abstraction
- exact pins
- metadata-only telemetry
- deterministic mock

Consumer services own:
- state construction
- question wording
- criteria
- candidate retrieval
- thresholds
- MATCH / NOT_MATCH / REVIEW decisions
- human review
- authoritative deterministic business rules
- evaluation datasets and calibration

Do NOT implement mastering-service logic in ai-core.

Do NOT implement auto-match, auto-merge, auto-approve or any authoritative
consumer action.

============================================================
9. STRICTLY FORBIDDEN J1 WORK
============================================================

Do NOT:
- add TypeSafe SDK
- implement Jev adapter
- implement Julia adapter
- implement kev adapter
- add provider credentials
- add network/endpoints
- promote JUDGMENT into current production provider catalog
- change provider_catalog.py
- change provider_aliases.py
- change capabilities.py
- change routing.py
- change transports.py
- change executor.py
- change __init__.py
- change pyproject.toml
- perform consumer migration
- modify mastering-service
- modify prozakupki-platform
- modify onprem-processing
- deploy or release
- tag
- create PR
- merge
- run hosted CI

Julia-1 is a future candidate only. J1 must remain generic enough that a future
Julia local adapter can map:
  Julia noul   -> Binary
  Julia choice -> Choice
  Julia score  -> Score
but do not add any Julia-specific runtime code or dependency now.

============================================================
10. REQUIRED VERIFICATION
============================================================

Run:

PYTHONPATH=.:src python3.10 -m pytest -q tests/test_judgment_*.py

PYTHONPATH=.:src python3.10 -m pytest -q \
  tests/test_v01_public_api_contract.py \
  tests/test_v031_hardening.py \
  tests/test_s1_privacy_egress.py \
  tests/test_s1_provider_catalog.py \
  tests/test_s3_runtime.py \
  tests/test_s3_executor.py

PYTHONPATH=.:src python3.10 -m pytest -q

python3.10 -m compileall -q src tools

PYTHONPATH=.:src python3.10 -c \
'import ai_core; import ai_core.judgment_contracts; import ai_core.judgment_validation; import ai_core.judgment_errors; import ai_core.judgment_runtime; import ai_core.judgment_privacy; import ai_core.judgment_telemetry; import ai_core.judgment_mock; print("J1_IMPORT_SMOKE_PASS")'

git diff --check

Verify protected runtime/public surface diff against exact base is EMPTY:

git diff a9548797c420b2a9d8b158b97a4cd48306c544db -- \
  src/ai_core/provider_catalog.py \
  src/ai_core/provider_aliases.py \
  src/ai_core/capabilities.py \
  src/ai_core/routing.py \
  src/ai_core/transports.py \
  src/ai_core/executor.py \
  src/ai_core/__init__.py \
  pyproject.toml

Canonical Make targets do not exist on this ai-core baseline.
Do not fabricate a Makefile.

Report them as:
- MAKE_TEST: NOT_RUN
- MAKE_TEST_REASON: CHECK_NOT_DEFINED_IN_TARGET_REPOSITORY
- MAKE_LINT: NOT_RUN
- MAKE_LINT_REASON: CHECK_NOT_DEFINED_IN_TARGET_REPOSITORY
- MAKE_SMOKE: NOT_RUN
- MAKE_SMOKE_REASON: CHECK_NOT_DEFINED_IN_TARGET_REPOSITORY

NOT_RUN is not PASS.

============================================================
11. COORDINATOR PROTOCOL
============================================================

Executor:
- edits code/spec/tests
- runs verification

Executor MUST NOT:
- git commit
- git push
- create/delete remote branches
- create PR
- trigger hosted CI
- merge

Coordinator owns:
- actual git-status inspection
- allowed/required-path enforcement
- exact-path staging
- deterministic commit
- non-force push
- remote publication SHA verification

Local operator creates Draft PR only AFTER:
publication_verified == true.

If any required work needs a file outside allowed paths, STOP with scope
expansion required rather than modifying it.

At completion print a structured EXECUTOR_REPORT containing:
- branch
- base SHA
- changed files
- focused J1 test result/count
- compatibility result/count
- full suite result/count
- compileall result
- import smoke result
- git diff --check
- protected runtime surface diff result
- MAKE_TEST / MAKE_LINT / MAKE_SMOKE NOT_RUN fields and reasons
- risks
- rollback
- J2=false
- network_calls_added=false
- credentials_added=false
- provider_sdk_added=false
- consumer_changes=false
- deployment_changes=false
- runtime_catalog_promotion=false
