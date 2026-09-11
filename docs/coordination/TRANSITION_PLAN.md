# Transition Plan — Coordinator v0.1 + Spec Kit (gradual)

Status: **transitional**
Date: 2026-09-11
Branch intent: `chore/coordinator-transition-v0.1-20260911`

## Non-negotiable

AI Core continues on the existing scheme:

```text
ChatGPT Architect ↔ docs/agent-bridge/** ↔ Cursor Executor
```

Coordinator v0.1 **overlays** that channel. It must not replace, rename, move,
or block `docs/agent-bridge/**`.

During transition, **`docs/agent-bridge/**` remains authoritative** for the
active Architect ↔ Executor loop.

## Why a Coordinator

Today a human must notice a new `next-prompt.md` and start Cursor manually.
v0.1 automates **only** that start gate:

```text
manual Cursor start  →  automatic Cursor start (when EXECUTOR_READY)
```

Everything after launch (commit, push, report publication) stays with the
existing Executor workflow until a later v0.2.

## Target transitional flow

```text
Architect
    ↓
docs/agent-bridge/next-prompt.md
    ↓
Coordinator (deterministic Python)
    ↓
Cursor Executor (at most once per invocation)
    ↓
existing execution / report convention
    ↓
docs/agent-bridge/latest-report.md
    ↓
Coordinator detects WAIT (or human stops)
    ↓
STOP
    ↓
Human says "Твой ход"
```

## Phased adoption

| Phase | What changes | What must not change |
| --- | --- | --- |
| v0.1 (this branch) | Optional Coordinator shadow/launch; docs; Spec Kit scaffold | Active bridge WAIT; in-flight S2/S2A; PR #3/#4/#5; runtime API |
| Finish current package | Complete S2/S2A under **old** bridge scheme | Do not mid-flight convert to Spec Kit |
| First suitable **new** package | Spec Kit–native planning/execution artifacts | Keep bridge as control channel until Architect says otherwise |
| v0.2 (future) | May move commit/push/report publication into Coordinator | Still no autonomous architectural decisions |

## Fail-closed defaults

- Legacy `# WAIT` → do nothing, exit cleanly.
- Missing / unknown / inconsistent Coordinator metadata → no launch.
- Dirty worktree, branch/SHA mismatch, missing declared worktree → `HUMAN_REQUIRED`.
- Hosted CI is never used as an iteration mechanism (see quota policy doc).

## Ownership evolution

```text
v0.1:   Executor owned edit + commit + push
v0.1.1: live-pilot-ready safety (claim/lock/bridge/repo)
v0.2:   Executor owns bounded edits; Coordinator owns
        postcondition validation + exact-path commit/push/verify
v0.2.1: optional declared transient_paths with baseline + exact cleanup
        (e.g. uv.lock) — never silent ignore, never .gitignore for agent
```
