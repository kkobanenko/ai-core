# Agent 3 revalidation — ai-core `v0.1.0` / `v0.2.0`

**Date (UTC):** 2026-07-25  
**Worktree (writer):** `/home/kok4444/projects/_coord_worktrees/ai-core-validate-v01-v02`  
**Branch:** `chore/validate-ai-core-v0.1-v0.2`  
**Base:** `83acc5304bd87451a0dc96d7a3b0ca663ec6769f` (`origin/main`)  
**Prior report:** `docs/handoffs/2026-07-16-ai-core-v010-v020-validation.md` (extended, not replaced)  
**RFC (read-only):** `/home/kok4444/projects/_coord_worktrees/platform-control-readonly/docs/rfc/AI-CORE-V0.3-RFC.md`

## Scope / bans observed

| Action | Done? |
|---|---|
| Validate immutable tags `v0.1.0` / `v0.2.0` | Yes |
| Start `v0.3` implementation | **No** |
| Create tags / releases | **No** |
| Change consumer pins | **No** |
| Deploy / merge | **No** |
| Writes outside this worktree | **No** |

## Tags and SHAs (reconfirmed)

| Tag | Annotated tag object | Peeled commit | On `main` / this branch |
|---|---|---|---|
| `v0.1.0` | `a77c105705bad956214d03bf01ca927c23238042` | `f7886b51ea4b87b734181a91de06644faaf0ef7e` | Yes (ancestor) |
| `v0.2.0` | `d3cb095ebcccaad94fbde5ffb3bd520733e394e9` | `e479d0af314714a96c959a2ea677abdcb0942af7` | **No** (lives on `ai-core-task2-tracing`) |

Topology note from 2026-07-16 still true: release lines diverge; do not rewrite tags.

## Packaging / clean-env results (Python 3.10.12)

Host still lacks `python3.12` locally. Prior Gate 2 CI evidence for 3.12 remains the alternate matrix source (`compatibility.yaml`).

| Cell | pytest | wheel build+install | HTTPS clean install (`git+https://…@tag`) |
|---|---|---|---|
| `v0.1.0` @ 3.10 | **15 passed** (0.09s) | **PASS** → `ai_core-0.1.0` | **PASS** (no credentials) |
| `v0.2.0` @ 3.10 | **20 passed** (0.63s) | **PASS** → `ai_core-0.2.0` | **PASS** (no credentials) |

Temp evidence root: `/tmp/ai-core-validate-agent3-rerun` (local only; not committed).

## Public API and backward compatibility

### Shared tracing surface (both tags)

- `PhoenixConfig`, `load_phoenix_config`, `init_tracing`, `shutdown_tracing`, `start_llm_span`, `maybe_truncate`
- Env defaults deterministic: `PHOENIX_ENABLED=false`, `PHOENIX_TRACE_INCLUDE_IO=false`, `max_io_chars=4000`
- Soft-fail when disabled / collector unavailable (no raise on consumer path)

### Breaking delta `v0.1.0` → `v0.2.0` (not drop-in)

| Removed in `v0.2.0` | Added in `v0.2.0` |
|---|---|
| `sanitize_attributes`, `AttributeValue`, `record_llm_result` | `ProviderConfig`, `build_chat_model`, `LangChainJsonClient`, `ProviderTransportError`, `JsonCompletion`, `AttemptRecord` |
| module `attributes.py` | module `safe_attributes.py` (`sanitize_span_attributes`) |

**Attribute allowlist rename (breaking for span metadata):**

- `v0.1.0`: `workflow`, `adapter`, `provider_id`, `model`, `latency_ms`, `status`, `error_type`, `fallback_mode`, `actor_role`, `request_id`
- `v0.2.0`: `workflow`, `source_*`, `llm.*`, `ai.adapter`

Acceptable only under transitional dual-pin matrix (Zoom→`v0.1.0`, Prozakupki→`v0.2.0`).

## Provider abstraction (`v0.2.0` only)

| Concern | Result |
|---|---|
| OpenAI-compatible | `transport="openai_compatible"` → `ChatOpenAI`, `max_retries=0`, timeout from config |
| Mistral-compatible | `name=="mistral"` → `ChatMistralAI`, `max_retries=0` |
| Ollama / local | `transport="ollama_native"` → `ChatOllama`, timeout in `client_kwargs` |
| Timeout / retry ownership | Per-request timeout on provider; provider SDK retries forced to 0; transport fallback owns multi-provider attempts |
| Fallback ownership | `LangChainJsonClient` single `with_fallbacks(..., exceptions_to_handle=(ProviderTransportError,))` |
| Nested fallback | **Absent** (one fallback chain only) |
| Unavailable / not-ready | Filtered by `is_ready()`; empty chain → `RuntimeError("AI client is disabled")` |
| Response schema | `JsonCompletion.raw_content` only — **no** JSON schema validation (consumer-owned) |
| Error normalization | Transport-eligible → `ProviderTransportError`; others re-raised unchanged (partial normalization) |
| Secret leak via spans | Allowlist drops keys/urls; `api_key` never a safe attribute |
| Audit / tracing hooks | `start_llm_span` + attempt_summary; business audit remains consumer-owned (`ai_call_audit` in Prozakupki) |

`v0.1.0` has **no** provider/fallback API (tracing-only), matching Zoom ownership model.

## Consumer compatibility (read-only)

| Consumer | Observed pin | Transport | Imports used | Compat verdict |
|---|---|---|---|---|
| Prozakupki `main` | `v0.2.0` | HTTPS in `services/zakupki-monitor/Dockerfile` | `LangChainJsonClient`, `ProviderConfig`, tracing helpers | **Compatible** with `v0.2.0` surface |
| Prozakupki hardening worktree | `v0.2.0` | SSH transitional | same family | Compatible; transport still transitional vs ADR-003 target |
| Zoom `backend` | `v0.1.0` HTTPS | `backend/pyproject.toml` | `init_tracing`, `shutdown_tracing`, **`record_llm_result`**, `start_llm_span` | **Compatible only with `v0.1.0`** — `record_llm_result` missing on `v0.2.0` |
| Clin-rec | not installed | — | — | Do **not** install `v0.2.0` (LangChain major clash) |

Pins were **not** changed by this agent.

## Compatibility matrix (ai-core perspective)

| Consumer | Pin | Python target | May install `v0.1.0` | May install `v0.2.0` | Notes |
|---|---|---|---|---|---|
| Prozakupki | `v0.2.0` | 3.10+ (images often 3.12) | tracing-only subset yes | **required** | Owns transport fallback via ai-core client |
| Zoom | `v0.1.0` | `>=3.12` | **required** | **forbidden** (until shim/v0.3) | Owns provider loop; needs `record_llm_result` |
| Clin-rec | none | 3.10/3.12 | optional later | **forbidden** | `langchain>=0.3,<1` vs ai-core 1.x pins |
| `ai-core` `main` | docs + `v0.1.0` line | `>=3.10` | N/A | provider code **absent** | Reconciliation deferred to RFC / separate initiative |

Canonical control-plane matrix: `platform-control/config/compatibility.yaml` (read-only here).

## Gaps mapped to merged RFC v0.3 (docs only — no implementation)

| Validated gap | RFC v0.3 response (proposed) |
|---|---|
| Divergent release lines (`v0.2.0` not on `main`) | §2 / §12 — restore linear history before cutting `v0.3.0` |
| Hard LangChain deps on any `v0.2.0` install | §1 / §2 — optional extras (`ai-core[langchain]`) |
| Breaking public API + allowlist rename | §1 / §3.3 — compatibility shim for both surfaces |
| Zoom blocked from `v0.2.0` (`record_llm_result`) | shim / dual export policy in RFC |
| No JSON schema acceptance in shared client | remains consumer-owned (RFC boundary) |
| Partial error normalization | RFC provider contract may tighten categories later |
| Local Python 3.12 absent | RFC requires 3.10 **and** 3.12 support; CI already evidenced 3.12 |
| Prozakupki SSH residual in some worktrees | ADR-003 HTTPS target; main already HTTPS |

**Explicit:** this branch does **not** implement RFC sections, extras, shims, or `v0.3.0` sources.

## Defects / fixes on this branch

| Item | Action |
|---|---|
| Tag defects requiring release rewrite | **None applied** (tags immutable) |
| Source bugfix on tagged lines | **None** — would require new patch release / reconciliation PR |
| Validation docs + v0.1 public-contract tests on branch | **Yes** (this commit) |

Notable non-blocking doc drift on tagged `v0.2.0` README: still shows SSH install example while ADR-003 / Prozakupki main use HTTPS. Fix belongs in a future release docs commit, not tag rewrite.

## Verdict

### **CONDITIONAL PASS** (reconfirmed)

Runnable `v0.1.0` / `v0.2.0` artifacts remain valid for transitional dual-pin consumption. Convergence, API unification, optional extras, and allowlist shim remain **RFC v0.3 / separate implementation initiative** work — not started here.

## Handoff

| Field | Value |
|---|---|
| Branch | `chore/validate-ai-core-v0.1-v0.2` |
| Base SHA | `83acc5304bd87451a0dc96d7a3b0ca663ec6769f` |
| Tests | `v0.1.0@3.10` 15 passed; `v0.2.0@3.10` 20 passed; HTTPS installs; API smokes; branch contract tests |
| Risks | 3.12 local still unrun; release-line divergence; Zoom cannot upgrade to `v0.2.0`; attribute key divergence |
| Rollback | Drop branch / PR; consumers keep existing immutable pins |
| `v0_3_implementation_started` | `false` |
| `release_created` | `false` |
