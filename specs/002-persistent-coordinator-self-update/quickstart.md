# Quickstart: Persistent Coordinator Self-Update

This quickstart describes the intended post-implementation operator flow. Commands become authoritative only after the **implementation package** is reviewed, merged, and locally available.

**Spec-only note**: This branch (`spec/002-persistent-coordinator-self-update-20260912`) contains requirements and plan only. No updater code or systemd units exist until the follow-on implementation package lands.

## Prerequisites

- Persistent Coordinator runner (`001-persistent-coordinator-runner`) implemented and activated on the workstation.
- Local Coordinator checkout on transition branch `chore/coordinator-transition-v0.1-20260911` with clean worktree and expected `origin`.
- User systemd session available.

## 1. Bootstrap boundary (one-time, after implementation review)

From the reviewed Coordinator tooling checkout, run the extended installer with explicit paths and enable the updater timer. The implementation must provide a command equivalent to:

```bash
python3.10 scripts/install_dev_coordinator_runner.py \
  --coordinator-repo /home/kok4444/projects/ai-core-coordinator-transition \
  --managed-worktree-root /home/kok4444/projects/.coordinator-worktrees \
  --repo kkobanenko/ai-core=/home/kok4444/projects/ai-core \
  --repo kkobanenko/platform-control=/home/kok4444/projects/platform-control \
  --agent-bin "$(command -v agent)" \
  --enable \
  --enable-updater
```

Expected effect:

- existing runner config/service unchanged in behavior;
- updater config written under `~/.config/ai-core-dev-coordinator/updater.json` (or documented equivalent);
- user units written:
  - `~/.config/systemd/user/ai-core-dev-coordinator-updater.service`
  - `~/.config/systemd/user/ai-core-dev-coordinator-updater.timer`
- `systemctl --user daemon-reload` performed;
- updater timer enabled and started;
- no sudo required.

**This is the last routine terminal activation** for Coordinator transition maintenance. After bootstrap, reviewed transition merges on GitHub should advance locally without manual `git fetch/merge` or `systemctl restart`.

Without `--enable-updater`, units/config may be written but automatic self-update does not run.

## 2. Verify updater and runner

```bash
systemctl --user status ai-core-dev-coordinator-updater.timer --no-pager
systemctl --user status ai-core-dev-coordinator-runner.service --no-pager
journalctl --user -u ai-core-dev-coordinator-updater.service -n 50 --no-pager
```

Expected: timer active; runner active; updater journal shows periodic attempts (often `NOOP` when already current).

## 3. Inspect updater status (read-only)

```bash
PYTHONPATH=/path/to/coordinator-checkout \
python3.10 -m tools.dev_coordinator.updater \
  --config ~/.config/ai-core-dev-coordinator/updater.json \
  --status
```

Should display:

- local Coordinator HEAD
- remote reviewed transition HEAD (when fetch succeeded)
- last attempt time and result (`NOOP`, `SUCCESS`, `SKIPPED`, `FAIL_CLOSED`)
- reason for skip/fail-closed

## 4. Normal future workflow (post-bootstrap)

1. Architect reviews and merges Coordinator tooling into `chore/coordinator-transition-v0.1-20260911` on GitHub.
2. Within ~1–2 minutes (default timer), updater fetches `origin`, verifies preconditions, and fast-forwards local checkout if clean and ff-only eligible.
3. If HEAD changed and maintenance gate + process lock prove no active scan/package, updater restarts the persistent runner once.
4. Operator continues using `Твой ход` / Architect bridge workflow without manual git or restart commands.

No per-update terminal command is required after bootstrap.

## 5. One-shot updater smoke test (before enabling timer)

```bash
PYTHONPATH=. python3.10 -m tools.dev_coordinator.updater \
  --config /path/to/test-updater.json \
  --once
```

Use a dedicated test clone. Do not enable the live timer until Architect approves.

## 6. When self-update skips or fails

Common recorded reasons:

| Reason | Meaning | Operator action |
| --- | --- | --- |
| `maintenance_held` | runner has active scan/package (shared maintenance) | wait; updater retries on next cycle |
| `process_lock_held` | manual one-shot Coordinator or lock contention | wait for one-shot to finish; updater retries |
| `dirty_worktree` | local uncommitted changes | commit/stash manually or reset intentionally |
| `diverged` | non-ff history | manual reconcile; updater will not force |
| `wrong_branch` / `wrong_origin` | checkout misconfigured | fix checkout to canonical transition clone |
| `ff_refused` | merge not fast-forward; state uncertain | inspect git log; manual recovery; runner may be stopped |
| `ff_refused_recoverable` | ff failed but checkout proven unchanged; runner restored once | inspect cause; updater retries on later cycle |
| `fetch_error` | network/auth issue | fix connectivity; retry |

Updater never auto-repairs these states.

## 7. Rollback self-update (keep runner)

Disable automatic updates while keeping the runner on its last known-good checkout:

```bash
systemctl --user disable --now ai-core-dev-coordinator-updater.timer
systemctl --user disable --now ai-core-dev-coordinator-updater.service
```

Runner service may remain enabled. Manual one-shot Coordinator remains available for emergency execution.

To roll back runner as well:

```bash
systemctl --user disable --now ai-core-dev-coordinator-runner.service
```

## Operational notes

- Default updater cadence is ~60 seconds; runner polling remains ~15 seconds — they are independent.
- Self-update never tracks `main`/`master` or feature branches.
- Maintenance gate: runner holds **shared** during scans; updater holds **exclusive** during update. Runner skips scans (without terminal failures) while updater maintains exclusive.
- Manual one-shot Coordinator does not use maintenance gate; updater holds Coordinator process lock during mutation so concurrent manual launch fails safely.
- A restarted runner may run under updater maintenance exclusive but will not process candidates until exclusive is released.
- Implementation and automated tests must not silently enable the live updater timer on the developer workstation.
- Hosted CI is forbidden for this feature unless separately authorized.
