# Architect Work-Package Publisher (v1)

Status: **implemented**

Date: 2026-09-16

## Purpose

Publish one bounded Architect work package with a single command instead of
manually creating target and `coord/bridge/*` branches.

The publisher is **Architect-side transport only**. It does not invoke
Coordinator or Executor.

## CLI

```bash
python3 /path/to/ai-core/scripts/publish_dev_coordinator_package.py \
  --runner-config ~/.config/ai-core-dev-coordinator/runner.json \
  --bridge-repo kkobanenko/ai-core \
  --target-repo kkobanenko/ai-core \
  --base-sha <exact-commit-sha> \
  --target-branch feat/my-feature \
  --package-id my-feature-001 \
  --prompt-id my-feature-001 \
  --allowed-paths path/a.py,path/b.py \
  --required-paths path/a.py,path/b.py \
  --transient-paths uv.lock \
  --commit-message "feat: my feature" \
  --hosted-ci forbidden \
  --instruction-file ./task-body.md \
  --dry-run
```

`--bridge-branch coord/bridge/...` may be used instead of `--package-id`.

`--json` prints machine-readable result only. Without `--dry-run`, the tool
performs non-force remote publication.

The CLI bootstraps `tools.*` from the script’s repository root and works from
any current working directory.

## Publication order

1. Validate inputs locally (allowlist, branch namespace, paths, SHA syntax).
2. Inspect target remote branch (`git ls-remote`).
3. Inspect bridge remote branch.
4. Create target remote branch at exact `base_sha` if absent (non-force push).
5. Verify target remote SHA equals `base_sha`.
6. Build bridge commit containing `docs/agent-bridge/next-prompt.md` via isolated
   `commit-tree` plumbing (no primary checkout/index mutation).
7. Push bridge branch (non-force).
8. Verify bridge remote SHA.
9. Print human-readable and JSON result.

The bridge is **never** published before the target branch is proven at
`base_sha`.

## Resume / idempotency

| Target remote state | Behavior |
| --- | --- |
| absent | create at `base_sha` |
| exactly `base_sha` | reuse (resumable) |
| any other SHA | **fail closed** |

| Bridge remote state | Behavior |
| --- | --- |
| absent | create commit + push |
| tip `next-prompt.md` identical to requested package | **idempotent** (no push) |
| tip content differs | **fail closed** |

Rerunning an identical already-published package does not create a second
logically different work package.

Interrupted publication may be resumed when target is already at `base_sha` and
bridge either does not exist yet or matches the same package content.

## Dry run

`--dry-run` performs validation and remote reads, renders exact `next-prompt.md`,
reports intended refs and derived `target_worktree`, and performs **no** git
mutation and no filesystem writes (except unavoidable read-only runtime).

## Safety

- Bridge and target repos must be in runner allowlist with canonical `origin`.
- Target branches `main`/`master` and `coord/bridge/*` are rejected.
- Bridge branches must be under `coord/bridge/`.
- No force push, `reset --hard`, `clean`, `checkout`/`switch`, `rebase`,
  `stash`, `pull`, or `merge` on primary checkouts.
- Primary checkout working tree and index are snapshotted before/after; dirty
  checkouts must remain byte/status-identical.

## Prompt format

Flat front matter (comma-separated path lists, no YAML lists) accepted by
`parse_next_prompt`. `target_worktree` is derived from runner
`managed_worktree_root` via `derive_executor_worktree_path` — callers must not
hand-construct it.

## API

```python
from tools.dev_coordinator.package_publisher import (
    WorkPackageSpec,
    publish_work_package,
)
```

See `tools/dev_coordinator/package_publisher.py` for `PublicationOutcome` fields.
