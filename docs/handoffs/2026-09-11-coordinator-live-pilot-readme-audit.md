# Coordinator live pilot — README / S1 drift audit

**Date:** 2026-09-11  
**Prompt ID:** `coordinator-live-pilot-readme-audit-001`  
**Status:** executor report complete; Architect review required  
**Pilot type:** documentation-only; no source/README modification in this run

## Governance and Git

| Field | Value |
|-------|-------|
| Branch | `docs/coordinator-live-pilot-readme-audit-20260911` |
| Base SHA | `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e` |
| Head SHA | `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e` (pre-commit; pending executor commit/push) |
| Target repo | `kkobanenko/ai-core` |
| Hosted CI | forbidden for this pilot |
| PR created | no |

### Bridge workflow conflict (recorded)

The legacy Coordinator v0.1.1 text asks the Executor to update
`docs/agent-bridge/latest-report.md` and archive under `docs/agent-bridge/**`.
The active `next-prompt.md` for this pilot explicitly forbids creating or
modifying `docs/agent-bridge/**` in the executor worktree and names this
handoff file as the GitHub-visible execution report.

**Resolution:** repository governance and the active pilot prompt win. This
report is published only under `docs/handoffs/`. No `docs/agent-bridge/**`
files were created or modified.

### Platform-control check

- Initiative registry read:
  `/home/kok4444/projects/platform-control/coordination/current-initiative.yaml`
- `ai_core_v0_3_implementation_authorized` remains `false` in backlog.
- No shared contracts, ports, provider/fallback behavior, or tracing semantics
  were changed in this run.
- No deployment lock was taken; no infrastructure action was performed.

## 1. What README currently says AI Core is

Evidence: `README.md` at audit time (unchanged by this run).

README describes **ai-core** as:

- A thin shared library for **Phoenix observability** in AI projects.
- Scope: env-based configuration, soft-fail tracing, and IO truncation in
  traces.
- Consumers: `prozakupki-platform`, `zoom-in-plan`, and future `clin-rec` as a
  git dependency (`@v0.1.0`).
- Explicitly **no credentials or business code**.
- Documents four Phoenix env vars (`PHOENIX_ENABLED`, `PHOENIX_COLLECTOR_ENDPOINT`,
  `PHOENIX_PROJECT_NAME`, `PHOENIX_TRACE_INCLUDE_IO`, `PHOENIX_TRACE_MAX_IO_CHARS`).
- Public API section is labeled **"Phase 1"** and lists only root exports:
  `init_tracing`, `maybe_truncate`, `shutdown_tracing`, `start_llm_span`,
  `PhoenixConfig`, `load_phoenix_config` (plus implied helpers via examples).
- Includes install, env tables, consumer examples, and a Phoenix UI smoke test
  via `examples/smoke_span.py`.

README does **not** mention provider identity, capability evidence, privacy /
egress contracts, submodule imports, or S1 foundation work.

## 2. What functionality is actually present (current worktree / S1 line)

Evidence inspected:

- `README.md`
- `src/ai_core/__init__.py`
- `src/ai_core/provider_catalog.py`
- `src/ai_core/capabilities.py`
- `src/ai_core/privacy.py`
- `src/ai_core/config.py`, `tracing.py`, `attributes.py`, `io_policy.py`
- `pyproject.toml`
- `tests/test_v01_public_api_contract.py`
- `tests/test_s1_*.py`
- `docs/handoffs/2026-09-11-ai-core-s1-foundation-contracts.md`

### Implemented — root public API (v0.1 tracing line; matches README Phase 1)

`ai_core.__all__` exports exactly **nine** symbols:

- `AttributeValue`, `PhoenixConfig`, `init_tracing`, `load_phoenix_config`,
  `maybe_truncate`, `record_llm_result`, `sanitize_attributes`,
  `shutdown_tracing`, `start_llm_span`

Behavior (current-main facts):

- Phoenix config from environment with safe defaults (`PHOENIX_ENABLED=false`,
  IO off, 4000-char truncate limit, local collector endpoint).
- Soft-fail tracing: disabled or misconfigured Phoenix does not crash callers.
- Attribute sanitization with a governed allowlist.
- IO truncation via `maybe_truncate`.
- LLM span helpers (`start_llm_span`, `record_llm_result`).
- Package version `0.1.0`; sole runtime dependency `arize-phoenix-otel==0.16.1`.
- `examples/smoke_span.py` for manual Phoenix UI verification.

### Implemented — S1 foundation contracts (submodule-only; **not** in root `__all__`)

Present in `src/ai_core/` and covered by `tests/test_s1_*.py`:

**`ai_core.provider_catalog`**

- Four canonical provider IDs:
  `vm100_local_ollama`, `gpu_ollama`, `ollama_cloud`, `mistral_external`.
- Immutable `ProviderIdentity` records with governed `NetworkBoundary` only
  (`LOCAL_SAME_HOST`, `EXTERNAL`, `UNKNOWN_BOUNDARY`).
- `get_provider_catalog()`, `get_provider_identity()`; unknown IDs raise
  `UnknownProviderIdentityError`.
- No endpoints, credentials, health, cost, latency, priority, or capability
  metadata.

**`ai_core.capabilities`**

- Pure vocabulary: `ProviderCapability` (text, structured_json, vision_image,
  ocr_pdf) and `CapabilityEvidenceLevel` (CONFIGURED → RUNTIME_OBSERVED,
  FAILED_INCONCLUSIVE).
- Immutable `CapabilityEvidence` scoped to provider + model + capability +
  boundary; boundary drift rejected.
- `has_runtime_observation()` — evidence flag only; not routing eligibility.

**`ai_core.privacy`**

- `DataClass` and `OutboundForm` enums.
- `is_egress_eligible()` pure pre-routing predicate: SECRET denied everywhere;
  external/unknown-boundary egress requires literal `request_egress_authorized=True`;
  fail-closed on non-enum inputs.

**Compatibility boundary (S1 facts)**

- Root import of `ai_core` does **not** load foundation modules.
- Foundation APIs require explicit submodule imports
  (`from ai_core.provider_catalog import ...`).
- `pyproject.toml` dependencies unchanged; no httpx/langchain/openai/ollama/
  mistral packages added.
- Tests document 71-pass S1 suite on the implementation branch per the prior
  S1 handoff (not re-run in this pilot).

### Historical donor context (not current-main behavior)

`docs/handoffs/2026-09-11-ai-core-s1-foundation-contracts.md` records that S1
ideas were reimplemented from read-only evidence on PR #3 head
`4e26d67b825194e489a6a8b553c2a53dfea2a81f` with deliberate semantic reduction.
That donor PR is **not** merged main behavior; it is provenance only.

## 3. README statements that are stale or incomplete

| README claim | Drift |
|--------------|-------|
| Library is only "Phoenix observability: config, soft-fail tracing, IO truncation" | **Incomplete.** Package also ships S1 governance contracts under submodule paths. README scope statement omits them entirely. |
| "Публичный API (Phase 1)" lists only tracing symbols | **Accurate for root `__all__`**, but **misleading as full package description** — readers cannot discover `provider_catalog`, `capabilities`, or `privacy` from README. |
| No submodule / compatibility-boundary guidance | **Missing.** S1 handoff and tests require explicit submodule imports; README silent. |
| Implies `@v0.1.0` tag surface equals documented API | **Incomplete.** Tag/0.1.0 root API is tracing-only; current S1-line worktree adds non-root modules without README mention. |
| Consumer install block shows only tracing env defaults | **Incomplete** for integrators who need foundation contracts (no import examples). |
| "Пакет не содержит credentials или business code" | Still **true**, but README does not clarify that S1 modules are **contracts only** — not runtime provider calls. Easy to over-read. |

Nothing in README is strictly **false** for the nine-symbol root export; the
drift is **omission and scope understatement** relative to the S1-line tree.

## 4. Functionality still explicitly absent

Current-main / S1-line facts — not proposed future architecture:

- No provider transport, HTTP clients, or LLM execution.
- No route planner, retry/fallback executor, health probes, deadlines, or cost/
  latency routing.
- No concrete model registry or shipped capability records establishing
  production eligibility.
- No provider aliases or ID resolution helpers.
- No `STT_SEGMENTS` capability.
- No additional provider identities beyond the governed four.
- No v0.2-style root symbols (`LangChainJsonClient`, `ProviderConfig`,
  `build_chat_model`, etc.) — guarded by `test_v02_provider_symbols_absent_on_main_line`.
- S1 contracts are **not** runtime enforcement; consumers must apply them
  separately.
- `ai_core_v0_3_implementation_authorized` remains false at platform-control;
  merge of S1 draft PR #6 is not authorized by this pilot.
- No service container, no microservice runtime, no deployment artifacts in this
  repository.

## 5. Proposed README update outline (for future review only)

**Not implemented in this pilot.** Suggested structure for a follow-up docs PR:

1. **Opening paragraph** — Retain Phoenix tracing as the primary consumer
   story; add one sentence that the package also exposes optional **S1
   foundation contracts** (identity, capability evidence, privacy/egress) via
   submodule imports only.

2. **"Root public API (v0.1 tracing)"** — Rename current "Phase 1" section;
   keep env table and tracing examples unchanged.

3. **"Foundation contracts (S1, submodule import)"** — New section:
   - `from ai_core import provider_catalog` / `capabilities` / `privacy` pattern.
   - One-line purpose per module.
   - Explicit note: not exported from `ai_core.__all__`; no side effects on
     `import ai_core`.

4. **"What is not in this package"** — Short bullet list mirroring section 4
   above (no runtime routing, no credentials, no model registry).

5. **Version / install** — Clarify whether `@v0.1.0` documents root-only
   surface; if S1 merges separately, state which tag or branch carries
   foundation modules.

6. **Cross-link** — Point to
   `docs/handoffs/2026-09-11-ai-core-s1-foundation-contracts.md` for contract
   detail and PR #6 status.

Do **not** document unmerged v0.2/v0.3 provider execution or invent future
architecture in README.

## Validation (this run)

| Check | Result |
|-------|--------|
| Only intended handoff file added | intended; verify with `git status` after commit |
| `git diff --check` | pending — shell/git tools rejected in executor session |
| README modified | no |
| `src/**` modified | no |
| `tests/**` modified | no |
| `.github/**` modified | no |
| `AGENTS.md` / `.cursor/rules/**` modified | no |
| `docs/agent-bridge/**` modified | no |
| Hosted CI requested | no |
| PR created | no |

## Risks

- README understatement may cause consumers to miss S1 contracts or assume
  tracing-only install is the full package.
- Submodule-only boundary is easy to break accidentally if someone adds
  foundation symbols to `__all__` without a governed ADR.
- This pilot does not re-run pytest; S1 test counts are cited from the prior
  S1 handoff.

## Rollback

Revert or drop commit on
`docs/coordinator-live-pilot-readme-audit-20260911` that adds only this file.
No production source, README, or consumer impact.

## Executor handoff

- **Branch:** `docs/coordinator-live-pilot-readme-audit-20260911`
- **Base SHA:** `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e`
- **Head SHA:** `f65221b4090a8d2e1fad7e3872e79ec52ec3ed5e` until commit lands; re-run `git rev-parse HEAD` after commit
- **Files changed:** `docs/handoffs/2026-09-11-coordinator-live-pilot-readme-audit.md`
- **Tests:** optional; not required for this documentation-only pilot
- **Risks:** see above
- **Rollback:** revert single docs commit; no source rollback needed
