# ai-core consumer compatibility matrix (validation snapshot)

Date: 2026-07-25  
Source of truth for platform policy remains `platform-control/config/compatibility.yaml`.  
This file is an ai-core-side validation snapshot only.

## Immutable tags

| Tag | Peeled SHA |
|---|---|
| `v0.1.0` | `f7886b51ea4b87b734181a91de06644faaf0ef7e` |
| `v0.2.0` | `e479d0af314714a96c959a2ea677abdcb0942af7` |

## Consumer pins (observed, not modified)

| Consumer | Pin | Install | Status |
|---|---|---|---|
| Prozakupki main | `v0.2.0` | HTTPS | Compatible |
| Zoom backend | `v0.1.0` | HTTPS | Compatible |
| Clin-rec | not installed | — | Keep uninstalled until Stage 0 / later gate |

## Cross-install rules

| From \ To | `v0.1.0` | `v0.2.0` |
|---|---|---|
| Prozakupki | tracing-only OK | required |
| Zoom | required | **breaking** (`record_llm_result` / allowlist) |
| Clin-rec | possible later | **forbidden** (LangChain major) |

## v0.3 mapping

Gaps (divergent history, hard LangChain deps, API/allowlist shim) are documented against merged RFC `AI-CORE-V0.3-RFC.md`. No v0.3 code on this branch.
