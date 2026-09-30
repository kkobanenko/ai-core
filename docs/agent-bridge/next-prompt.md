---
coord_version: 1
state: EXECUTOR_READY
prompt_id: AI-SEMANTIC-JUDGMENT-J1-CONTRACT-01
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
commit_message: feat(judgment): implement J1 provider-neutral contract
transient_paths: uv.lock
---

# AI-SEMANTIC-JUDGMENT-J1-CONTRACT-01

Executor: Local Coordinator + Headless Cursor CLI.
Repository: kkobanenko/ai-core.
Authorized exact base:
a9548797c420b2a9d8b158b97a4cd48306c544db

Operator authorization:
AUTHORIZE_J1_CONTRACT_ONLY
scope=contract_only.

The previous PLAN_ONLY/HOLD_J1 wording in specs/003-judgment-provider predates
the current operator authorization and MUST NOT be interpreted as a current HOLD.

Current governance state:
ADR-023 Accepted.
G0 CLOSED.
G1 CLOSED.
G2/J1 OPEN.
J1 contract_only authorized.

Read and follow:
- AGENTS.md
- specs/003-judgment-provider/spec.md
- specs/003-judgment-provider/plan.md
- specs/003-judgment-provider/tasks.md

Implement only J1 provider-neutral contract.

Required implementation surfaces:
- src/ai_core/judgment_contracts.py
- src/ai_core/judgment_validation.py
- src/ai_core/judgment_errors.py
- src/ai_core/judgment_runtime.py
- src/ai_core/judgment_privacy.py
- src/ai_core/judgment_telemetry.py
- src/ai_core/judgment_mock.py

Required focused tests:
- tests/test_judgment_contracts.py
- tests/test_judgment_validation.py
- tests/test_judgment_privacy.py
- tests/test_judgment_runtime.py
- tests/test_judgment_telemetry.py
- tests/test_judgment_fail_closed.py

Contract requirements:
- provider-neutral JudgmentProvider, not TextProvider and not prompt-to-JSON;
- immutable typed Choice, Score, Noul;
- typed JudgmentRequest / JudgmentResponse;
- exactly one response variant: choice+score OR Noul OR normalized error;
- declared choices only;
- finite bounded Score;
- explicit Noul reason, never implicit approval;
- exact decision_pack id/version and criterion identifier;
- exact provider/model/version pins;
- reject wildcard/*-latest judgment pins;
- deterministic request and response validation;
- free-form provider output never reaches consumer logic;
- one monotonic total deadline;
- one retry/fallback owner;
- normalized judgment errors;
- privacy/egress gate before provider invocation;
- metadata-only telemetry;
- deterministic in-memory mock_judgment only.

Canonical normalized errors:
invalid_request
privacy_egress_denied
deadline_exhausted
rate_limited
authentication_failed
provider_unavailable
transport_failed
invalid_provider_response
internal_error

Privacy contract:
- hosted/external judgment test doubles permit only SYNTHETIC and PUBLIC_NO_PII;
- explicit egress authorization required for external boundary;
- PRIVATE_CLIENT_DATA must never reach external judgment provider;
- SECRET denied;
- unknown boundary denied;
- denied request => provider/mock invocation count = 0.

Strictly forbidden:
- J2;
- real typesafe_jev adapter;
- real kev_local adapter;
- provider SDK;
- credentials;
- endpoints;
- network calls;
- deployment;
- release/tag;
- consumer migration;
- provider admission;
- production/live execution;
- automatic actions;
- authoritative decisions;
- changes to mastering-service/prozakupki-platform/onprem-processing;
- VM100 changes;
- automatic procurement/entity/master-data decisions.

Do NOT modify existing runtime/provider surfaces merely to register JUDGMENT:
- src/ai_core/provider_catalog.py
- src/ai_core/provider_aliases.py
- src/ai_core/capabilities.py
- src/ai_core/routing.py
- src/ai_core/transports.py
- src/ai_core/executor.py
- src/ai_core/__init__.py

Do not modify pyproject.toml or add dependencies.
Standard library only.

mock_judgment is test-only:
- no network;
- no credentials;
- not provider_catalog;
- not default candidate;
- not production selectable.

Telemetry default must exclude:
prompt, response text, payload, payload fragments, Choice value, Score value,
credentials, secret and raw provider output.

Do not implement consumer-owned behavior such as:
model/effort fallback, context preservation, needs_review routing,
queue changes, low-confidence domain routing or tool selection.

Minimal changes to specs/003-judgment-provider/{spec,plan,tasks}.md are allowed
only if needed to reconcile stale pre-authorization wording.
Do not claim J2/release/provider admission.
J011 exact-head human review remains pending.

There is no Makefile on this baseline.
Do NOT create one.
make test/lint/smoke are NOT_RUN_TARGET_UNAVAILABLE.

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

PYTHONPATH=src python3.10 - <<'PY'
import ai_core
import ai_core.judgment_contracts
import ai_core.judgment_validation
import ai_core.judgment_errors
import ai_core.judgment_runtime
import ai_core.judgment_privacy
import ai_core.judgment_telemetry
import ai_core.judgment_mock
print("J1_IMPORT_SMOKE_PASS")
PY

git diff --check

Also verify the diff against the base for all protected runtime/public surfaces is empty.

IMPORTANT COORDINATOR PROTOCOL:
Do NOT git commit.
Do NOT git push.
Do NOT create PR.
Do NOT create/delete remote branches.
Coordinator owns commit and push.
Operator will create the Draft PR after Coordinator publication.

At completion print a structured EXECUTOR_REPORT containing:
- branch;
- base SHA;
- changed files;
- focused J1 test count/result;
- compatibility test count/result;
- full suite count/result;
- compileall result;
- import smoke result;
- git diff --check result;
- risks;
- rollback;
- confirmation J2=false;
- network_calls_added=false;
- credentials_added=false;
- consumer_changes=false;
- deployment_changes=false;
- runtime_catalog_promotion=false.

If any required scope expansion is necessary, STOP rather than implementing it.
