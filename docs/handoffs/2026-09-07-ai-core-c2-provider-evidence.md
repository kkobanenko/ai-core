# ai-core C2 — provider/model evidence reconciliation

## Status

**Branch:** `feat/ai-core-provider-evidence-c2-20260907`  
**Base branch:** `feat/ai-core-consolidation-foundation-20260907`  
**Base SHA:** `4e26d67b825194e489a6a8b553c2a53dfea2a81f`  
**Merge authorization:** **BLOCKED_PENDING_PLATFORM_CONTROL_REVIEW**  
**Review request:** `kkobanenko/platform-control#291`

No consumer repository, release, tag, deployment, or production configuration is changed by C2.

## Goal

Reconcile provider names and model capabilities observed in current consumers without copying consumer YAML into ai-core and without changing the v0.1 root tracing API.

## Changes

### Provider identity

Canonical IDs continue to represent provider/network identities, not individual task chains.

Foundation identities retained:

- `vm100_local_ollama`
- `ollama_cloud`
- `gpu_ollama`
- `mistral_external`

Proposed C2 additions, pending platform-control acceptance:

- `gpu_whisper`
- `openai_external`
- `deepseek_external`

`gpu_ollama` and `gpu_whisper` remain `UNKNOWN_BOUNDARY`. Current private-overlay/Tailscale reachability is not treated as proof of an accepted trusted boundary. Their sensitive RAW policy therefore remains DENY.

### Aliases

Explicit migration aliases live in `ai_core.provider_aliases`:

- `ollama_local -> vm100_local_ollama`
- `local_gpu_ollama -> gpu_ollama`
- `local_gpu_vision -> gpu_ollama`
- `local_gpu_whisper -> gpu_whisper`
- `mistral` / `mistral_ocr -> mistral_external`
- `openai -> openai_external`
- `deepseek -> deepseek_external`

Generic `ollama` is deliberately **ambiguous** and raises instead of guessing a local/cloud network boundary. `fake` remains consumer/test-local and is not promoted to a canonical production provider identity.

### Model capability evidence

`ProviderCapability` adds `STT_SEGMENTS` as a proposed first-class capability.

Historical v0.2.2 profiles remain present. Current observed profiles are added with non-secret evidence references, including:

- `gpu_ollama / qwen3.6:35b` — TEXT + STRUCTURED_JSON
- `gpu_ollama / qwen3-vl:4b` — TEXT + VISION_IMAGE
- `gpu_whisper / Systran/faster-whisper-large-v3` — STT_SEGMENTS
- `vm100_local_ollama / qwen3.5:9b` — TEXT + STRUCTURED_JSON
- `ollama_cloud / gemma4` — TEXT + STRUCTURED_JSON
- `mistral_external / ministral-8b-2512` — TEXT + STRUCTURED_JSON + VISION_IMAGE
- `mistral_external / mistral-ocr-latest` — OCR_PDF
- `mistral_external / voxtral-mini-latest` — STT_SEGMENTS
- `openai_external / gpt-4o-mini-2024-07-18` — TEXT + STRUCTURED_JSON
- `openai_external / whisper-1` — STT_SEGMENTS
- `deepseek_external / deepseek-chat` — TEXT + STRUCTURED_JSON

A profile marked `CURRENT_OBSERVED` means the capability/model pairing is present in current consumer configuration/evidence. It does not claim the model is installed or healthy in every deployment.

## Security / compatibility invariants

- root `ai_core.__all__` is untouched;
- no LangChain/httpx dependency is added;
- canonical catalog contains provider-specific credential env names only;
- no secret values are stored in catalog or evidence metadata;
- unknown provider aliases fail closed;
- unknown model capabilities fail closed;
- generic `ollama` fails as ambiguous;
- external providers deny sensitive RAW;
- local GPU identities remain RAW-denied until their network boundary is explicitly accepted.

## Governance finding

`platform-control/config/compatibility.yaml` currently has an accepted provider/privacy policy naming only four identities (`vm100_local_ollama`, `ollama_cloud`, `gpu_ollama`, `mistral_external`). C2 therefore must not be merged as an accepted canonical contract until platform-control review decides whether the three additional identities and `STT_SEGMENTS` belong in the compatibility contract.

This handoff does not resolve any `pending_decision` or the control-plane `operator_decision_required` state.

## Tests

Target suite:

```bash
python -m pytest -q
```

Expected coverage:

- existing v0.1 exact root API contract;
- foundation privacy/provider tests;
- alias ambiguity/unknown failure paths;
- current model capability/evidence tests;
- STT capability tests.

CI result is recorded in the stacked PR after GitHub Actions completes.

## Risks

1. Provider identity expansion conflicts with the currently accepted compatibility matrix until reviewed.
2. `ProviderProfile.supports_*` legacy booleans remain text-oriented; future C3 routing must combine privacy eligibility with **model capability**, rather than treating those booleans as modality truth.
3. Consumer generic credential fallbacks such as `AI_API_KEY` are intentionally not canonicalized; migrations may need explicit compatibility adapters.
4. Model evidence can drift; evidence metadata makes drift visible but does not itself perform runtime model discovery.
5. `UNKNOWN_BOUNDARY` blocks RAW private media on local GPU identities. This is intentionally safer than matching current behavior without a governance decision.

## Rollback

C2 is a stacked, unmerged branch. Rollback is to close/drop the C2 PR and retain the green foundation branch/PR #3 unchanged. No consumer or production rollback is required because C2 performs no deployment or consumer modification.
