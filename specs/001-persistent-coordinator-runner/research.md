# Research: Persistent Coordinator Runner

## Decision 1 — Long-running user service vs per-package manual launch

**Decision**: Use a long-running `systemd --user` service with an internal 15-second polling loop.

**Why**: It removes the remaining per-package terminal action, survives terminal closure, and gives standard service/journal observability. The existing one-shot Coordinator remains the execution primitive.

**Alternatives considered**:

- Manual `nohup` per package: rejected because this is the exact friction being removed.
- `systemd` timer invoking a scan process every interval: viable, but a persistent service gives simpler in-memory serialization and less repeated process startup while still being supervised/restarted.
- GitHub Actions/webhook-driven execution: rejected for quota, local Cursor dependency, credentials, and because hosted CI must not become the iteration engine.

## Decision 2 — Poll remote refs, do not watch arbitrary filesystem prompts

**Decision**: Poll allowlisted local git clones, fetch `origin`, and discover only `refs/remotes/origin/coord/bridge/*`.

**Why**: GitHub remains durable source of truth; Architect can create the remote branches using current GitHub tooling; a unique new prefix prevents accidental execution of historical bridge branches.

**Alternatives considered**:

- Scan every historical `test/*` branch: rejected as unsafe; old EXECUTOR_READY prompts exist.
- Watch a local directory/inbox: rejected because Architect cannot write directly to the user's local filesystem.
- One permanent queue file on one branch: possible later, but would require new concurrency/append/ack semantics and would bypass proven remote-branch verification patterns.

## Decision 3 — Architect creates remote branches; runner never invents remote work

**Decision**: Target and bridge remote branches must already exist. Runner only prepares local managed worktrees.

**Why**: This keeps architectural intent/publication with Architect and makes persistent runner a deterministic transport executor, not a planner.

**Rejected**: Having the runner create target branches from metadata. That would enlarge authority and complicate fail-closed review.

## Decision 4 — Reuse one-shot Coordinator unchanged as much as possible

**Decision**: Runner invokes `tools.dev_coordinator.cli.run_once` or the equivalent tested CLI path after preparing worktrees.

**Why**: Existing claim acquisition, bridge verification, governance loading, transient handling, postconditions, exact-path commit/push, and remote verification already passed live pilots. Reimplementing them inside the daemon would duplicate safety-critical logic.

## Decision 5 — Strict managed worktree root

**Decision**: Every automatically created/reused worktree must live below one configured managed root.

**Why**: A remote prompt must not be able to point automation at arbitrary directories. This also allows collision checks and future safe cleanup.

**Rejected**: Trusting any absolute `target_worktree` from the prompt.

## Decision 6 — No automatic claim recovery

**Decision**: Preserve current exactly-once claim semantics. If the runner or machine dies after claim acquisition, do not automatically reclaim.

**Why**: Automatic reclaim could duplicate partially completed agent actions. Exceptional stuck claims remain an explicit Architect/operator recovery case.

## Decision 7 — Persistent local terminal state supplements, never replaces, Coordinator claims

**Decision**: Store terminal `(bridge repo, branch, SHA)` results locally to avoid repeated invocation/log noise.

**Why**: The service polls continuously; without a local terminal index it would repeatedly feed unchanged prompts into Coordinator. The Coordinator claim is still the security authority; runner state is only scheduling/idempotency optimization and observability.

## Decision 8 — Initial repository allowlist is deliberately small

**Decision**: Support only `kkobanenko/ai-core` and `kkobanenko/platform-control` at activation.

**Why**: These are the repositories already exercised by Coordinator cross-repo workflows. Extending persistent execution to KMO, Prozakupki, or others changes blast radius and should be explicit.

## Decision 9 — One-time operator activation remains required

**Decision**: Code implementation and tests do not silently install/start a service. After Architect review, the operator runs one explicit install/enable command.

**Why**: Enabling an always-on process is a workstation operational change. The goal is to eliminate per-package commands, not to hide activation.

## Decision 10 — Spec Kit authority, bridge transport

**Decision**: For this package and future suitable packages, Spec Kit feature artifacts define requirements/plan/tasks. `docs/agent-bridge/next-prompt.md` carries only the bounded executable work package and references the spec.

**Why**: This is the agreed post-S2A transition: Spec Kit owns what/why/plan/tasks; Coordinator remains deterministic execution guard.
