---
coord_version: 1
state: EXECUTOR_READY
prompt_id: architect-work-package-publisher-v1-001
target_repo: kkobanenko/ai-core
target_branch: feat/003-architect-work-package-publisher-v1-20260916
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/feat-003-architect-work-package-publisher-v1-20260916
base_sha: d210b96713ca47247b805cf9653940a1000f91f2
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: tools/dev_coordinator/package_publisher.py,scripts/publish_dev_coordinator_package.py,tests/test_package_publisher.py,docs/coordination/WORK_PACKAGE_PUBLISHER.md
required_paths: tools/dev_coordinator/package_publisher.py,scripts/publish_dev_coordinator_package.py,tests/test_package_publisher.py,docs/coordination/WORK_PACKAGE_PUBLISHER.md
publication_commit: true
publication_push: true
commit_message: feat: add architect work-package publisher
transient_paths: uv.lock
---

# Task: Architect Work-Package Publisher v1

Implement the missing Architect -> Persistent Runner publication layer.

The existing Persistent Runner, Coordinator, managed-worktree and publication
contracts are authoritative. Do not create a parallel execution framework.

## Deliverables

Create exactly these intended work-product files:

1. tools/dev_coordinator/package_publisher.py
2. scripts/publish_dev_coordinator_package.py
3. tests/test_package_publisher.py
4. docs/coordination/WORK_PACKAGE_PUBLISHER.md

Do not modify any other tracked file.

## User-facing goal

After this work is reviewed and landed, an Architect must be able to publish
one bounded work package with one command instead of manually creating target
and coord/bridge branches.

The CLI must be usable from an unrelated current working directory. Do not
assume cwd is the ai-core repository; another project may contain its own
top-level tools package.

## Existing contracts to reuse

Read and reuse the existing current contracts, especially:

- tools/dev_coordinator/runner_config.py
- tools/dev_coordinator/managed_worktrees.py
- tools/dev_coordinator/parse.py
- tools/dev_coordinator/gitutil.py
- docs/coordination/PERSISTENT_RUNNER.md
- docs/coordination/COORDINATOR_RUNBOOK.md
- docs/coordination/ARCHITECT_EXECUTOR_PROTOCOL.md

The publisher is Architect-side transport creation only.
It must not invoke Executor itself.

## Required publisher behavior

The publisher must accept enough declarative input to construct an
EXECUTOR_READY work package, including at minimum:

- runner config path
- bridge repo
- target repo
- exact base SHA
- target branch
- bridge branch or deterministic package identifier
- prompt_id
- allowed_paths
- required_paths
- optional transient_paths
- commit message
- hosted_ci policy
- instruction body from a file

Use existing Runner configuration as the authority for repository clone paths
and managed_worktree_root.

Derive target_worktree using the existing managed-worktree path contract.
Do not ask the caller to hand-construct it.

## Safety requirements

Fail closed.

The tool must:

- require the bridge and target repositories to be in the Runner allowlist;
- canonicalize and verify repository origins;
- reject target branch main/master;
- reject target branches in coord/bridge namespace;
- require bridge branches to be inside coord/bridge/;
- validate exact base SHA as a commit;
- verify remote target branch state before mutation;
- never overwrite a target branch at an unexpected SHA;
- never force push;
- never use reset --hard;
- never use git clean;
- never use checkout/switch on the primary checkout;
- never use rebase;
- never use stash;
- never use git pull;
- never modify the primary checkout working tree;
- never modify the primary checkout index;
- work correctly when the primary checkout is dirty;
- never merge, create a PR, tag, release, or deploy.

Prefer Git plumbing with an isolated temporary index/object construction, or
another isolated mechanism that gives equivalent proof that the primary
working tree and index are untouched.

## Publication order

The safe publication order must be:

1. validate everything possible locally;
2. inspect target remote branch;
3. inspect bridge remote branch;
4. create target remote branch at the exact base SHA if absent;
5. verify exact target remote SHA;
6. create the bridge commit containing docs/agent-bridge/next-prompt.md;
7. publish the bridge branch without force;
8. verify exact bridge remote SHA;
9. print a machine-readable and human-readable result.

The bridge must never be published before the target branch is proven to
exist at the declared base SHA.

## Resume / idempotency

Design for interrupted publication.

At minimum:

- if target remote already exists exactly at base_sha, it may be reused;
- target remote at any other SHA must fail closed;
- rerunning an identical already-published package must not silently create a
  second logically different work package;
- changed package content under an existing bridge branch must fail closed.

Document the exact resume semantics.

## Dry run

Provide a --dry-run mode that:

- performs validation and remote reads;
- renders the exact next-prompt content;
- reports intended refs and managed worktree path;
- performs no git mutation and no filesystem mutation outside unavoidable
  read-only runtime behavior.

Tests must prove the dry-run mutation boundary.

## Prompt format

Generate the current flat front matter accepted by parse_next_prompt.

Do not emit YAML lists.

Path collections must use the current comma-separated flat metadata format.

Generated prompt must successfully round-trip through parse_next_prompt.

## Implementation boundaries

Standard library only.

Do not change Runner polling semantics.
Do not change Coordinator execution semantics.
Do not add hosted-CI execution.
Do not add PR merge behavior.
Do not add deployment behavior.
Do not change src/ai_core/**.

## Tests

Use isolated temporary git repositories and/or injected git runners.
Tests must not push to real GitHub and must not start systemd services.

Cover at least:

- prompt rendering parses successfully with parse_next_prompt;
- deterministic target worktree derivation;
- unrelated cwd / local tools-package shadowing does not break CLI bootstrap;
- dirty primary checkout is preserved byte/status-identically;
- target branch absent -> exact-base creation path;
- target branch exact base -> resumable path;
- target branch wrong SHA -> fail closed;
- bridge outside coord/bridge -> fail closed;
- existing bridge with differing package -> fail closed;
- identical package rerun is safe/idempotent;
- dry-run makes no refs/working-tree/index mutation;
- no forbidden destructive Git commands are issued.

Run the targeted publisher tests and the existing Coordinator test suite
relevant to runner/package parsing/publication.

Do not start or restart live services.

At completion, summarize:
- exact files changed;
- tests run/results;
- commit SHA;
- remote branch SHA;
- any limitation requiring Architect review.
