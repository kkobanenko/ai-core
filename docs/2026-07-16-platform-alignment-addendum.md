# Platform Alignment Addendum — ai-core

**Date:** 2026-07-16  
**Control plane:** `/home/kok4444/projects/platform-control`  
**Initiative:** `ai-foundation-v2`  
**Base SHA:** `f959e9a906035a5b3dbb5113a8a481159007f47d`

## Scope

This addendum aligns `ai-core` with accepted platform-control decisions for shared AI observability, optional provider helpers, distribution, and release-line validation. It does not authorize product migrations or a new major release.

## Controlling platform decision

Gate 1 decisions in platform-control are authoritative for shared ai-core/Phoenix/fallback/rollout questions:

- `docs/adr/ADR-001-ai-core-boundary.md` (Accepted)
- `docs/adr/ADR-002-canonical-phoenix.md` (Accepted)
- `docs/adr/ADR-003-ai-core-distribution.md` (Accepted)
- `coordination/gate-1-decision-record.md`
- `config/compatibility.yaml`

## Accepted ADR references

| ADR | Decision |
|---|---|
| ADR-001 | Option 2: tracing + optional provider/transport primitives; consumer owns orchestration/validation |
| ADR-002 | Canonical Phoenix remains Prozakupki compose source under platform governance |
| ADR-003 | Public HTTPS immutable tag distribution |

## Immutable tags

- `v0.1.0` — stable shared tracing API (`f7886b51ea4b87b734181a91de06644faaf0ef7e`)
- `v0.2.0` — optional provider/fallback API for compatible consumer (`e479d0af314714a96c959a2ea677abdcb0942af7e`)

These tags must not be rewritten.

## Boundary rules

- `v0.1` surface: stable shared tracing API.
- `v0.2` surface: optional provider/fallback API for a compatible consumer (currently Prozakupki).
- Nested fallback is forbidden.
- Product-specific business code must not move into ai-core.
- Domain validation and schema acceptance remain in consumers.

## Distribution

- Public HTTPS pin format: `ai-core @ git+https://github.com/kkobanenko/ai-core.git@vX.Y.Z`
- No branch installs for shared consumers.
- No embedded credentials for the public dependency.

## Gate 2 obligations

- Verify Python 3.10/3.12 where applicable for `v0.1.0` and `v0.2.0`.
- Reconcile current `main` versus `v0.2.0` tag (tag may not be on `main`) without rewriting history/tags.
- Verify public HTTPS clean install.
- Do not create `v0.3.0` in this initiative (`v0.3` is deferred).

## Allowed work now

- tests;
- clean install verification;
- release-line analysis.

## Prohibited now

- rewrite tags;
- provider redesign beyond accepted boundary;
- product migration from this repository task;
- release `v0.3.0`.

## Rollback

Consumers roll back by pinning the previous immutable tag and restoring their prior adapter/fallback path. Shared tags remain immutable.

## Handoff requirements

Any ai-core Gate 2 handoff must include exact branch, base SHA, head SHA, tests run, risks, and rollback pin. Only one writer may change ai-core at a time.
