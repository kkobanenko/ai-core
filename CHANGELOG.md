# Changelog

## 0.3.3 - 2026-10-04

### Added
- **Canonical J1 JudgmentProvider contract**: Canonical provider-neutral `JudgmentProvider` contract supporting batch-first named questions (`BinaryQuestion`, `ChoiceQuestion`, `ScoreQuestion`) and answers (`BinaryAnswer`, `ChoiceAnswer`, `ScoreAnswer`).
- **J1 Execution**: Deterministic mock-only execution.

### Changed
- **GPU trust boundary**: `gpu_ollama` is `INTERNAL_TRUSTED` (`internal_trusted`). It is not `LOCAL_SAME_HOST` and not `UNKNOWN_BOUNDARY`. `INTERNAL_TRUSTED` allows every valid non-SECRET data class, including `PRIVATE_CLIENT_DATA`, without external-cloud egress authorization. `SECRET` stays denied for every boundary and every outbound form. `EXTERNAL` and `UNKNOWN_BOUNDARY` still require literal `request_egress_authorized=True`.
- **Transport gate**: `execute_transport_attempt` uses the same `is_egress_eligible` decision as the planner. A `gpu_ollama` fallback no longer raises `EgressNotAuthorizedError` when the egress flag is false. A non-loopback endpoint override still requires literal `True` for both `LOCAL_SAME_HOST` and `INTERNAL_TRUSTED`. Provider identities and aliases are unchanged.

## 0.3.1 - 2026-09-17

### Fixed
- **Policy Authorization Hardening**: `_build_default_policy` now strictly validates candidates against `CANONICAL_PROVIDER_IDS`, preventing self-authorizing rogue candidates when no explicit policy is passed.
- **Candidates Defaulting Fix**: Fixed `candidates or DEFAULT_CANDIDATES` bug where `candidates=[]` was coerced to default providers. An empty list now correctly raises `NoEligibleProviderError`.
- **Deadline Starvation Protection**: `SingleLoopRuntime` now allocates `reserve_per_future_attempt_seconds` to guarantee downstream fallback candidates receive adequate budget.
- **Endpoint Separation**: Separated default endpoints for `vm100_local_ollama` (`11434`), `gpu_ollama` (`11435`), and `ollama_cloud` (`https://api.ollama.com`), preventing fallback collisions.
- **Deadline Root-Cause Chaining**: `RequestDeadlineExceededError` is now chained via `__cause__` and observable via `AllCandidatesExhaustedError.is_deadline_exceeded`.
- **HTTP 404 Fallback**: HTTP 404 is now classified as `fallback_eligible = True` and `terminal = False`, enabling fallback when a specific model is missing on a provider.
- **Health Store Synchronization**: Router and runtime now share the same `health_store` instance when a custom `runtime` is passed to `execute_chat`.
- **Package Metadata**: Synchronized `pyproject.toml` version to `0.3.1` and added package `__version__`.

## 0.3.0 - 2026-09-17

### Added
- **S3 Single-Loop Runtime Engine**: Deterministic sequential fallback over planned `RouteCandidate` sequence under shared time budget.
- **S3 Executor Ergonomics**: High-level `execute_chat` and `execute_prompt` facade integrating planning, egress checks, and runtime execution.
- **S2B Provider Transports**: Single-attempt HTTP transports for Ollama and Mistral APIs.
- **S2A Provider Aliases**: Aliases and network boundary classification.
- **S1 Foundation Contracts**: Bounded routing, capabilities, privacy, and health store.

## 0.2.0 - 2026-07-25

### Added
- Multi-project Phoenix telemetry bridge and IO truncation policy.

## 0.1.0 - 2026-07-16

- Initial public release of metadata-safe Phoenix tracing foundation.
