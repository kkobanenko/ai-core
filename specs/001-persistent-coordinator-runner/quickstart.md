# Quickstart: Persistent Coordinator Runner

This quickstart describes the intended post-implementation operator flow. Commands become authoritative only after the feature is implemented, reviewed, and merged.

## 1. One-time activation

From the reviewed Coordinator tooling checkout, run the installer with explicit repository mappings and enable the user service. The implementation must provide an idempotent command equivalent to:

```bash
python3.10 scripts/install_dev_coordinator_runner.py \
  --coordinator-repo /home/kok4444/projects/ai-core-coordinator-transition \
  --managed-worktree-root /home/kok4444/projects/.coordinator-worktrees \
  --repo kkobanenko/ai-core=/home/kok4444/projects/ai-core \
  --repo kkobanenko/platform-control=/home/kok4444/projects/platform-control \
  --agent-bin "$(command -v agent)" \
  --enable
```

Expected effect:

- config written under `~/.config/ai-core-dev-coordinator/runner.json`;
- user unit written under `~/.config/systemd/user/ai-core-dev-coordinator-runner.service`;
- `systemctl --user daemon-reload` performed;
- service enabled and started;
- no sudo required.

## 2. Verify service

```bash
systemctl --user status ai-core-dev-coordinator-runner.service --no-pager
journalctl --user -u ai-core-dev-coordinator-runner.service -n 100 --no-pager
```

Expected: service is active and polling. Idle state is normal.

## 3. Normal future workflow

No terminal command is required per package.

1. User writes `Твой ход` in ChatGPT.
2. Architect reviews GitHub and produces Spec Kit artifacts/work package.
3. Architect creates a target remote branch at exact base SHA.
4. Architect creates a bridge branch under `coord/bridge/<package-id>` containing `docs/agent-bridge/next-prompt.md` with `EXECUTOR_READY` metadata and a managed target-worktree path.
5. The local runner detects the branch automatically.
6. Runner prepares managed worktrees and invokes one-shot Coordinator.
7. Coordinator launches Cursor exactly once, validates edits, commits/pushes exact paths and verifies remote HEAD.
8. User later writes `Твой ход`; Architect reviews remote results.

## 4. Inspect runner status

The implementation must provide a read-only status command equivalent to:

```bash
PYTHONPATH=/home/kok4444/projects/ai-core-coordinator-transition \
python3.10 -m tools.dev_coordinator.runner \
  --config ~/.config/ai-core-dev-coordinator/runner.json \
  --status
```

It should show the latest candidates/results without launching work.

## 5. One-shot discovery smoke test

Before live activation, the runner can be exercised without a long-running loop:

```bash
PYTHONPATH=. python3.10 -m tools.dev_coordinator.runner \
  --config /path/to/test-runner.json \
  --once
```

A harmless dedicated `coord/bridge/*` smoke package should be used. Do not repurpose historical bridge branches.

## 6. Stop/rollback persistent mode

```bash
systemctl --user disable --now ai-core-dev-coordinator-runner.service
```

After disabling, the existing manual one-shot Coordinator remains available.

## Operational notes

- The machine and user systemd session must be running for automatic execution.
- Temporary network failure should delay detection, not lose the package.
- A fail-closed or consumed-claim anomaly may still need explicit recovery; the service must never auto-reclaim an exactly-once claim.
- Adding another repository to the persistent allowlist is an explicit operator/config change, not something a remote prompt can request.
