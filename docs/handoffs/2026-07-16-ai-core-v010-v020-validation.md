# Gate 2 validation — ai-core `v0.1.0` / `v0.2.0`

**Date (UTC):** 2026-07-16T17:32:26Z  
**Repository:** `/home/kok4444/projects/ai-core`  
**Control plane:** `/home/kok4444/projects/platform-control`  
**Initiative:** `ai-foundation-v2` / `gate_2_shared_release_validation`  
**Writer scope:** validation report only (no source/tag/remote/VM100 changes)

## Preconditions (launch gate)

| Check | Result |
|---|---|
| ADR-001 status | Accepted |
| ADR-002 status | Accepted |
| ADR-003 status | Accepted |
| Initiative current gate | `gate_2_shared_release_validation` |
| ai-core addendum | `docs/2026-07-16-platform-alignment-addendum.md` present |

Launch conditions satisfied; validation proceeded.

## Repository inventory

| Field | Value |
|---|---|
| Branch | `main` |
| Local HEAD (before this report commit) | `784060cc3c8079e27535ca0585d4047183179832` |
| `origin/main` | `f959e9a906035a5b3dbb5113a8a481159007f47d` |
| Dirty status at inventory | clean working tree; branch ahead of origin by 1 (addendum commit already present) |
| Default branch (GitHub) | `main` |
| Visibility | `PUBLIC` (`gh repo view kkobanenko/ai-core`) |
| Remote | `git@github.com:kkobanenko/ai-core.git` (fetch/push) |

### Tags

| Tag | Annotated tag object | Peeled commit | Type | On remote |
|---|---|---|---|---|
| `v0.1.0` | `a77c105705bad956214d03bf01ca927c23238042` | `f7886b51ea4b87b734181a91de06644faaf0ef7e` | annotated | yes (`git ls-remote`) |
| `v0.2.0` | `d3cb095ebcccaad94fbde5ffb3bd520733e394e9` | `e479d0af314714a96c959a2ea677abdcb0942af7` | annotated | yes (`git ls-remote`) |

Remote peeled commits match local peeled commits. Tags were not rewritten during this task.

### Main / tag topology

| Fact | Evidence |
|---|---|
| `main` contains `v0.1.0` | `git merge-base --is-ancestor v0.1.0 main` → yes; `git branch -a --contains v0.1.0` → `main`, `origin/main` |
| `main` does **not** contain `v0.2.0` | `git merge-base --is-ancestor v0.2.0 main` → no |
| Branches containing `v0.2.0` | `ai-core-task2-tracing`, `origin/ai-core-task2-tracing` |
| Graph shape | `v0.2.0` lives on a divergent line from common ancestor `92828dc`; `main` continued with tracing hardening + docs (`d2c0919` … `784060c`) |

This topology is recorded only. No merge/rebase/tag move was performed.

## Validation worktrees (left in place)

Paths were free before creation. `.worktrees/` is not tracked by Git (appeared as untracked; not staged).

| Worktree | HEAD | Tag |
|---|---|---|
| `.worktrees/platform-validation-v010` | `f7886b51ea4b87b734181a91de06644faaf0ef7e` | `v0.1.0` (detached) |
| `.worktrees/platform-validation-v020` | `e479d0af314714a96c959a2ea677abdcb0942af7` | `v0.2.0` (detached) |

`main` was not switched between tags. Pre-existing unrelated worktree `/tmp/ai-core-task2` was not deleted.

Temporary validation venvs lived under `/tmp/ai-core-gate2-validation-782927` and may be removed after review.

## Python tooling

| Tool | Result |
|---|---|
| `python3.10` | `Python 3.10.12` (`/usr/bin/python3.10`) |
| `python3.12` | **BLOCKER — not installed** (`command 'python3.12' not found`; anaconda has 3.9 only) |
| `uv` | `uv 0.7.8` |
| System package install via sudo/apt | not used |

## Python matrix

| Tag | Python 3.10 | Python 3.12 |
|---|---|---|
| `v0.1.0` | **PASS** — pytest / build / wheel install / import | **BLOCKER** — interpreter absent (not simulated) |
| `v0.2.0` | **PASS** — pytest / build / wheel install / import | **BLOCKER** — interpreter absent (not simulated) |

### Python 3.10 details

| Cell | pytest | build | wheel install | import smoke |
|---|---|---|---|---|
| `v0.1.0` / 3.10 | **15 passed** (0.10s), exit 0 | `ai_core-0.1.0-py3-none-any.whl`, exit 0 | exit 0 | `metadata.version=0.1.0`; file under `site-packages/ai_core/` |
| `v0.2.0` / 3.10 | **20 passed** (1.30s), exit 0 | `ai_core-0.2.0-py3-none-any.whl`, exit 0 | exit 0 | `metadata.version=0.2.0`; file under `site-packages/ai_core/` |

Install method per cell: isolated venv → `pip install -e '.[dev]'` → pytest → `python -m build` → clean venv → `pip install <wheel>` → import.

## Public HTTPS clean-install smoke

Command form (isolated temporary venvs, `GIT_TERMINAL_PROMPT=0`, no `SSH_AUTH_SOCK`):

```text
pip install "ai-core @ git+https://github.com/kkobanenko/ai-core.git@v0.1.0"
pip install "ai-core @ git+https://github.com/kkobanenko/ai-core.git@v0.2.0"
```

| Tag | pip exit | version | load path | credentials / SSH required |
|---|---|---|---|---|
| `v0.1.0` | 0 | `0.1.0` | `.../site-packages/ai_core/__init__.py` (not local editable / not worktree `src`) | no |
| `v0.2.0` | 0 | `0.2.0` | `.../site-packages/ai_core/__init__.py` | no |

## API validation

Existing tag tests were executed as primary evidence. Additional temporary smoke commands were used without modifying tagged sources/tests.

### `v0.1.0`

| Concern | Result |
|---|---|
| Tracing config (`PhoenixConfig` / `load_phoenix_config`) | OK — defaults `enabled=False`, `trace_include_io=False`, `max_io_chars=4000` |
| Metadata-only default | OK — `PHOENIX_TRACE_INCLUDE_IO` default false |
| `init_tracing` / `shutdown_tracing` / `start_llm_span` | OK when disabled (returns/`yield` None; no crash) |
| Soft-fail disabled Phoenix | OK |
| Soft-fail unavailable collector | Consumer path does not raise; `register` may succeed locally while async export fails — app API remains non-fatal |
| IO truncation policy | OK — `maybe_truncate` + allowlist via `sanitize_attributes` |
| Covered by pytest | `tests/test_config.py`, `test_io_policy.py`, `test_tracing.py`, `test_attributes.py` (15 total) |

### `v0.2.0`

| Concern | Result |
|---|---|
| Shared tracing imports (`PhoenixConfig`, `load_phoenix_config`, `init_tracing`, `shutdown_tracing`, `start_llm_span`, `maybe_truncate`) | OK |
| `ProviderConfig` / `build_chat_model` | OK — constructs `ChatOllama` for ready config |
| `LangChainJsonClient` transport-only fallback | OK via existing tests (`test_transport_error_falls_back`, retryable 429/503) |
| Non-transport errors terminal | OK (`ValueError` terminal; malformed success does not fallback) |
| Metadata-only default | OK |
| Safe attribute allowlist | OK — `sanitize_span_attributes`; secrets/URLs dropped |
| No project-specific business code in package modules | OK — no `prozakupki` / `zoom-in-plan` / `clin-rec` / `vm100` markers in `src/ai_core/*.py` |
| Public symbol delta vs `v0.1.0` | **Note:** `sanitize_attributes`, `record_llm_result`, `AttributeValue` are **not** on `v0.2.0` public `__all__` (allowlist module renamed to `safe_attributes`). Acceptable only because consumers are pinned to distinct release lines per compatibility matrix |

## Dependency comparison

### Declared (`pyproject.toml`)

| | `v0.1.0` | `v0.2.0` |
|---|---|---|
| `requires-python` | `>=3.10` | `>=3.10` |
| Required deps | `arize-phoenix-otel==0.16.1` (exact pin) | `arize-phoenix-otel` (unpinned), `opentelemetry-api`, `opentelemetry-sdk`, `langchain-core==1.4.9`, `langchain-ollama==1.1.0`, `langchain-mistralai==1.1.6`, `langchain-openai==1.3.5`, `httpx>=0.27,<1` |
| LangChain major | none | **1.x** (exact pins on core/providers) |
| Resolved freeze size (wheel env) | 22 packages | 63 packages |

### Known consumer compatibility (from platform-control matrix + observed constraints)

| Consumer | Transitional pin | Compatibility note |
|---|---|---|
| Prozakupki | `v0.2.0` | Applicable — needs provider/JSON transport fallback API |
| Zoom | `v0.1.0` | Remains on tracing-only line; avoids LangChain 1.x pull and keeps consumer-owned provider loop |
| Clin-rec | not installed until Stage 0 | **Do not install `v0.2.0`** — Clin-rec declares `langchain>=0.3,<1`, incompatible with ai-core `langchain-core==1.4.9` |

## Release-line analysis (no fix applied)

Observed: `main` includes `v0.1.0` ancestry plus later docs/hardening; immutable tag `v0.2.0` points at commit `e479d0a` on `ai-core-task2-tracing`, which is **not** an ancestor of `main`.

### Recommendation for a **separate** follow-up task (not executed here)

Prefer **merge/reconciliation without tag rewrite**:

1. Plan a dedicated reconciliation PR that integrates the `v0.2.0` feature line into `main` (merge or equivalent), preserving both immutable tags.
2. Do **not** move `v0.2.0` onto `main` by retagging; do **not** invent `v0.2.1`/`v0.3.0` in this initiative unless a later ADR/gate authorizes it.
3. If product risk of merging is high, an explicit decision to **keep the divergent release line** until a later release is acceptable, but must remain documented in compatibility.yaml.

Patch release is unnecessary for Gate 2 evidence itself; the tags already validate as immutable artifacts.

## Blockers

1. **Python 3.12 unavailable** on the validation host → matrix cells for 3.12 not executed.
2. Gate 2 initiative still requires **consumer addendum acknowledgements** (outside this ai-core-only task).
3. **Release-line divergence** (`v0.2.0` not on `main`) remains open for a separate reconciliation task.

## Gate 2 verdict

### **CONDITIONAL PASS**

Rationale:

- Runnable cells on Python 3.10 for both immutable tags passed (tests, build, wheel install, import).
- Public HTTPS clean install for both tags passed without credentials.
- API smoke + existing tests support accepted boundary for transitional pins.
- Incomplete: Python 3.12 matrix; release-line reconciliation deferred; consumer acknowledgements out of repo scope.

### Exact conditions to proceed toward consumer compatibility (Gate 3)

1. Install/provide Python 3.12 on a validation host and re-run the missing four matrix cells (`v0.1.0`/`v0.2.0` × pytest/build/import), **or** obtain an explicit platform-control exception documenting 3.12 evidence from an alternate approved runner.
2. Keep consumer pins aligned with compatibility.yaml: Prozakupki → `v0.2.0`; Zoom → `v0.1.0`; Clin-rec → no ai-core until Stage 0 / later gate.
3. Collect consumer addendum acknowledgements required by Gate 2 work items.
4. Open (but do not block consumer contract *design* on) a separate reconciliation task for `main` vs `v0.2.0` topology without rewriting tags.

## Confirmation of non-mutation

| Surface | Changed? |
|---|---|
| Source code under tags / `src/` | **No** |
| `pyproject.toml` | **No** |
| Tests | **No** |
| README | **No** |
| Tag objects / tag targets | **No** |
| Remote (`push`) | **No** |
| Other repositories | **No** |
| VM100 / Phoenix operations | **No** |
| Allowed change | This validation report (+ local docs commit only) |

## Handoff

| Field | Value |
|---|---|
| Branch | `main` |
| Base SHA (origin/main at validation) | `f959e9a906035a5b3dbb5113a8a481159007f47d` |
| Head SHA before report commit | `784060cc3c8079e27535ca0585d4047183179832` |
| Tests run | `v0.1.0@3.10`: 15 passed; `v0.2.0@3.10`: 20 passed; HTTPS install smokes; API smokes |
| Risks | 3.12 unvalidated; `v0.2.0` not on `main`; LangChain major conflict if `v0.2.0` installed into Clin-rec/Zoom |
| Rollback | Consumers remain on prior immutable tag pins; no shared tag rewrite required |

## Artifacts retained for user review

- `.worktrees/platform-validation-v010`
- `.worktrees/platform-validation-v020`
- Temporary venv/log root (optional cleanup): `/tmp/ai-core-gate2-validation-782927`
