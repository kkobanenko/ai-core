# AI Core Compatibility Characterization Design

## Purpose

Build an automated, evidence-backed safety net before any AI Core runtime,
transport, routing executor, service, or consumer migration work. The suite
must protect current tracing-only behavior, preserve useful historical
inference contracts as separate evidence, normalize consumer infrastructure
requirements without copying product logic, and make governance conflicts
executable and visible rather than silently resolving them.

## Scope and invariants

This package may add tests, synthetic fixtures, reference snapshots, test-only
utilities, static/ref inspection scripts, CI checkout depth required for
immutable-tag inspection, and one technical report. It must not change any
production module, dependency manifest, consumer repository, platform-control
decision, provider identity, capability acceptance, runtime, service,
transport, feature flag, infrastructure, release, tag, or `main`.

The protected production baseline remains
`main@7569441c18362cfd15524ad73f56f7f35580c86f`. The work starts from the
previous documentation handoff
`65a865e5eef38e44559d98ab9187d5d59b8fa2e7` so that inventory provenance and
the new report remain together. User-owned `.worktrees/` content and `uv.lock`
outside this agent-owned worktree remain untouched.

## Selected approach

Use a hybrid of executable Git-ref characterization, portable synthetic
fixtures, isolated subprocess probes, and an explicit conflict ledger.

This is stronger than committed snapshots alone because immutable tag content
is checked against the actual Git objects. It is more portable than making the
default suite depend on neighboring consumer checkouts. Consumer sources are
read through recorded Git SHAs only by a separate local verifier; CI consumes
the normalized synthetic fixtures.

Rejected alternatives:

1. **Snapshots only.** Portable, but a stale or hand-edited snapshot could lose
   provenance without detection.
2. **Live cross-repository tests in the default suite.** They detect consumer
   drift, but make ai-core CI depend on checkout layout, repository access, and
   potentially dirty feature branches.
3. **Installing every historical dependency set.** This would reproduce the
   dependency conflicts the package is intended to isolate and could require
   network access/provider SDKs. Static API inspection plus narrow test stubs
   characterizes the required behavior without provider calls.

## Test architecture

### 1. Current v0.1 live contract

Add focused tests under `tests/compatibility/` that import the current package
and lock:

- exact root exports and direct imports;
- signatures, keyword-only parameters, defaults, return behavior, and public
  dataclass fields;
- Phoenix-disabled soft failure and order independence;
- metadata allowlisting, IO default-off behavior, truncation, and shutdown
  no-op safety;
- absence of historical inference symbols from the current root until a
  separately approved additive compatibility decision exists.

These tests characterize the package that actually executes on `main`; they do
not create a future root API.

### 2. Dependency-light subprocess probe

Run a fresh Python 3.10 subprocess with the repository `src` path inserted and
an import guard that raises if tracing-only import tries to load:

- `langchain` or any `langchain_*` package;
- `httpx`;
- OpenAI, Mistral, Ollama, or other provider SDK modules;
- a future AI Core client/server/runtime module.

The subprocess imports `ai_core`, exercises disabled tracing, and emits a small
JSON result. It performs no network call and inherits no credentials. The test
also inspects `sys.modules` to prove the forbidden dependency families were not
loaded indirectly.

### 3. Immutable historical ref characterization

Add a test-only Git object reader that accepts an exact SHA and path, never a
mutable branch. Characterization tests parse source and `pyproject.toml`
directly from:

- `v0.1.0@f7886b51ea4b87b734181a91de06644faaf0ef7e`;
- `v0.2.0@e479d0af314714a96c959a2ea677abdcb0942af7`;
- `v0.2.1@f743057a02a8b69bf943b615510d4745d737e16a`;
- `v0.2.2@679b88fa7cd6e9f64b543c405a90b2ef0dcdc575`.

The tests lock root exports, function/class signatures, dataclass fields,
invocation methods, capability names, and dependency families. A narrow
isolated loader supplies fake provider objects to the historical JSON client
and verifies observable fallback behavior without importing real SDKs or
calling a provider:

- providers are constructed lazily;
- each provider is attempted once;
- timeout, transport, HTTP 429, and HTTP 5xx advance to fallback;
- terminal 4xx stop;
- exhaustion returns the historical structured error/attempt evidence;
- domain schema acceptance is not performed by ai-core.

Historical tests deliberately do not import those symbols into current
`ai_core`. Their purpose is provenance and compatibility evidence.

The CI checkout may be changed to `fetch-depth: 0` so immutable tags are
available. Tests fail clearly when a required immutable tag object is missing;
they do not fetch from the network at test time.

### 4. Consumer representability fixtures

Create one schema-versioned synthetic JSON fixture per material consumer:

- Prozakupki;
- KMO;
- Zoom;
- Clin-rec;
- Landing Sell;
- agent-lab;
- Alpha University;
- transcription-service;
- image-description-service.

Every fixture records only infrastructure facts: evidence repository/SHA/file,
current AI path, ai-core pin or HTTP contract, historical provider/model names,
required capability, timeout/retry/fallback ownership, privacy/egress
requirement, tracing dependency, rollback path, and governance status. Fixtures
must not contain prompts, domain schemas, production payloads, endpoint values,
credential values, personal data, or product workflow code.

Portable tests validate the fixture schema and cross-consumer invariants:

- every inventory consumer is represented;
- each fallback chain has one declared owner;
- durable job retry is distinguished from provider-call retry;
- old pins/absence-of-pin remain explicit;
- media requirements do not imply accepted capabilities or an available
  server;
- required environment variables are names only;
- ambiguous aliases are marked ambiguous rather than auto-resolved;
- every transition has an explicit old-path rollback state.

A separate read-only verifier accepts a workspace root, reads the recorded
consumer commit with `git show <sha>:<path>`, extracts a small allowlisted set
of facts, and compares them with the fixtures. The verifier never reads secret
values, imports consumer code, modifies a consumer, or contacts a provider.
It is mandatory for this work package's local validation but not for portable
ai-core CI where neighboring repositories may be unavailable.

### 5. Privacy and conflict ledger

Create a matrix fixture that separates four states for every relevant rule:

- current behavior;
- historical behavior;
- desired safety invariant;
- proposed PR behavior;
- accepted/pending governance status.

The desired invariant is:

```text
SECRET -> BLOCK/DROP
```

for `RAW`, `SANITIZED`, and `SURROGATED`, and for local, external, and unknown
boundaries. Tests cover alias resolution, no-route behavior, retry/fallback
transitions, and transformed-state transitions so none can turn a SECRET into
an eligible request implicitly.

Because current `main` has no production privacy module, the desired matrix is
a reusable contract fixture, not a new runtime policy. Where the pinned PR #3
source is available, an isolated characterization test executes its
dependency-light privacy modules and proves the exact discrepancy: PR #3
blocks `SECRET + RAW` but permits `SECRET + SANITIZED/SURROGATED` for profiles
that allow sanitized data. The test passes only when the contradiction remains
explicit in the ledger; it does not silently patch PR #3.

### 6. PR #3–#5 pinned evidence

Record the observed head SHAs and normalized contract facts for each draft:

- #3 `4e26d67b825194e489a6a8b553c2a53dfea2a81f`;
- #4 `1b2569a612968a3ac5099dea955cfccdcb191d52`;
- #5 `25c269bb93dd37bd9b1556051972f5e1e60b34ad`.

When those Git objects exist locally, static tests compare the pinned source
with the evidence snapshot. If a PR object is absent in a clean clone, the
portable snapshot remains testable and the ref-match test reports a skip with
the missing SHA; immutable release-tag checks never skip.

The PR contract fixture covers:

- root API preservation and dependency boundaries;
- provider/model evidence levels and governance status;
- SECRET behavior;
- error taxonomy mapping gaps;
- health isolation and `UNKNOWN` eligibility;
- route-order authority;
- explicit egress authorization defaults;
- retry/fallback owner and absence of an executor;
- deadline arithmetic versus actual enforcement.

Tests assert that pending decisions remain pending and that proposed identities
or `STT_SEGMENTS` are not labeled accepted.

## Utilities and data flow

Test-only utilities have narrow responsibilities:

1. `git_ref.py`: read a blob from an exact local SHA and verify tag peeling.
2. `ast_contract.py`: extract exports, signatures, classes, enums, and dataclass
   fields without importing historical dependencies.
3. `historical_loader.py`: load only selected historical modules under a unique
   temporary package name with explicit fake dependencies.
4. `fixture_contract.py`: validate fixture schema and secret-free content.
5. workspace verifier script: compare allowlisted facts from consumer Git blobs
   to committed fixtures.

No helper is installed with the package; all live under `tests/` or `scripts/`
and are excluded from production imports.

## Determinism and safety

- No test uses the network, provider endpoint, live credential, wall-clock
  sleep, random provider choice, or production payload.
- Git reads use exact SHAs. Consumer working trees and untracked files are not
  read as authority.
- Subprocesses receive an allowlisted environment with provider credentials
  removed and Phoenix explicitly disabled.
- Fixtures use synthetic placeholders and validate against likely secret-value
  patterns.
- Assertions distinguish characterization (what exists) from requirements
  (what future code must satisfy) and governance (what is accepted).
- A known contradiction is represented by a passing conflict assertion, never
  by weakening the desired invariant or leaving the suite red.

## Technical report

Create
`docs/reports/2026-09-09-ai-core-compatibility-characterization-report.md`
inside this project worktree. It will contain the requested executive summary,
repository state, v0.1 and v0.2.x findings, consumer matrix, privacy/dependency
results, detailed PR #3–#5 recommendations, test-group explanations,
validation commands, governance questions, risks, target refinements, next
work package, and handoff.

The report records a pre-report content SHA and states that the exact final
delivery SHA is obtained with `git rev-parse HEAD`, because a commit cannot
embed its own hash.

## Validation

Minimum final validation:

```text
PYTHONPATH=src python3.10 -m pytest -q
python3.10 scripts/verify_consumer_contract_fixtures.py --workspace-root /home/kok4444/projects
git diff --check
```

Additional checks verify:

- no changed production source or consumer file;
- no network-capable test path;
- no credential values or product payloads in fixtures;
- deterministic repeated test results;
- immutable tag/ref provenance;
- current `main` and user-owned `.worktrees/`/`uv.lock` remain unchanged.

## Exit criteria

The package is complete when:

1. current v0.1 observable behavior and dependency-light import are executable
   contracts;
2. immutable v0.2.x APIs/dependencies and critical fallback semantics are
   characterized separately;
3. every material consumer has a validated synthetic infrastructure fixture;
4. the SECRET all-form/all-boundary invariant and PR #3 discrepancy are
   explicit and tested;
5. PR #3–#5 technical/governance conflicts are pinned and actionable;
6. all local validation passes with no provider calls or credentials;
7. the technical report permits a new agent to continue without reconstructing
   the investigation from chat history.

Passing this package does **not** authorize runtime implementation. The next
step remains bounded by platform-control review and the unresolved decisions
listed in the report.
