# Spec Kit adoption (gradual, non-disruptive)

## Principle

Do **not** convert the in-flight S2 / S2A package mid-flight.

```text
current / in-flight package  →  finish under the old agent-bridge scheme
first suitable NEW package   →  Spec Kit native
```

Existing Cursor rules and `AGENTS.md` remain in force. Spec Kit must
**coexist**, not overwrite governance.

## Official source

- Repository: [github/spec-kit](https://github.com/github/spec-kit)
- Install via official `specify-cli` from a **pinned release tag**

Pinned on this transition branch after install:

```text
specify-cli / Spec Kit: v1.0.6
git ref: 96c9bd657bfd5de0d651a6165084932b7304ac99
integration: cursor-agent
```

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v1.0.6
specify version
specify init --here --force --non-interactive --integration cursor-agent --ignore-agent-tools
```

Cursor integration key is `cursor-agent` (skills under `.cursor/skills`), not a
replacement for `.cursor/rules/**`.

Post-init inspection on 2026-09-11: `AGENTS.md` and `.cursor/rules/**` were
**not** modified. Scaffold added `.specify/**` and `.cursor/skills/speckit-*`
only. Constitution file remains the upstream placeholder template until a
future package authorizes a real constitution pass.

## Hard stop conditions

After any Spec Kit init/generate, inspect the full diff. **STOP and report** if
generated content overwrites or silently rewrites:

- `AGENTS.md`
- `.cursor/rules/**`
- existing platform-control managed blocks
- existing `docs/agent-bridge/**`

Prefer restoring those paths and documenting the conflict over “fixing
forward” through governance damage.

## Relationship to agent-bridge

During transition:

- `docs/agent-bridge/**` stays the authoritative Architect ↔ Executor channel;
- Spec Kit artifacts (constitution/spec/plan/tasks) are prepared for the
  **next** suitable package;
- Coordinator v0.1 does not require Spec Kit to function.

## Suggested first Spec Kit–native package criteria

A package is a good Spec Kit pilot when:

1. It is **new** (not mid-flight S2A);
2. Scope fits a single constitution/spec/plan cycle;
3. Architect explicitly authorizes Spec Kit as the planning surface;
4. Bridge metadata (or explicit human start) still gates Executor launch.

## Out of scope here

- Replacing ChatGPT Architect with Spec Kit alone
- Forcing Executor to abandon `latest-report.md` convention in v0.1
- Mid-flight rewrite of S2 discovery outcomes
