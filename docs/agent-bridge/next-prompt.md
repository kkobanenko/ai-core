---
coord_version: 1
state: EXECUTOR_READY
prompt_id: architect-work-package-publisher-review-fix1-001
target_repo: kkobanenko/ai-core
target_branch: feat/003-architect-work-package-publisher-v1-20260916
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/feat-003-architect-work-package-publisher-v1-20260916
base_sha: 2d6fd7ad2c6fcec3ba99ad7e5669ff570482dc78
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: tools/dev_coordinator/package_publisher.py,scripts/publish_dev_coordinator_package.py,tests/test_package_publisher.py,docs/coordination/WORK_PACKAGE_PUBLISHER.md
required_paths: tools/dev_coordinator/package_publisher.py,tests/test_package_publisher.py
publication_commit: true
publication_push: true
commit_message: fix: harden architect work-package publisher
transient_paths: uv.lock
---

# Architect Work-Package Publisher v1 — review fix 1

Continue the existing publisher implementation from exact base:

2d6fd7ad2c6fcec3ba99ad7e5669ff570482dc78

Do not rewrite the subsystem and do not change existing Runner or Coordinator
execution semantics.

## Review finding P0: bridge objects become unreachable before push

The current _create_commit_with_prompt implementation creates blob/tree/commit
objects with GIT_OBJECT_DIRECTORY pointing at a TemporaryDirectory.

The helper returns the new commit SHA and exits its TemporaryDirectory context.
The temporary object store is then deleted.

publish_work_package subsequently attempts:

git push origin <returned-sha>:refs/heads/<bridge>

In a real repository the returned commit may therefore no longer exist in any
object store reachable by the push.

Fix this architectural defect.

A preferred simple design is:

- keep an isolated temporary GIT_INDEX_FILE;
- allow generated blob/tree/commit objects to live in the repository object
  database;
- prove that the primary checkout HEAD, branch, working tree and real index are
  unchanged.

An alternative design that keeps a temporary object store is acceptable only
if its lifetime provably extends through bridge push and remote verification.

Do not use checkout, switch, reset, clean, rebase, stash, pull or force push.

## Review finding P1: injected Git tests are not truthful

Current _git_runner_with_env accepts base_runner but ignores it and directly
executes subprocess git.

This means tests using FakeRemoteState do not faithfully exercise all commands
that production executes.

Refactor this boundary so tests cannot report successful publication while
environment-sensitive Git plumbing is bypassing the injected test transport.

It is acceptable to separate:
- unit-testable decision/publication sequencing; and
- explicitly real-Git plumbing.

But the distinction must be clear and tested.

## Mandatory real-Git integration test

Add a non-dry-run integration test using temporary local repositories only.

The test must use:

- a real working clone;
- a local bare remote;
- canonical GitHub repository identity for origin;
- local Git URL rewriting if necessary so the canonical GitHub-looking origin
  actually pushes to the local bare remote.

The test must execute the real publisher without mocking publication Git.

It must prove all of the following:

1. target branch absent initially;
2. publisher creates target remote branch exactly at base_sha;
3. publisher creates a real bridge commit;
4. publisher successfully pushes that exact bridge commit after commit creation;
5. bridge remote contains docs/agent-bridge/next-prompt.md;
6. remote prompt content exactly equals the rendered requested package;
7. rerunning the identical package is idempotent;
8. target and bridge refs do not move on identical rerun;
9. dirty primary checkout remains unchanged;
10. primary Git index remains unchanged.

This test must fail against the current P0 implementation before the fix, or
otherwise explicitly demonstrate why the previous implementation was invalid.

No network and no GitHub access in tests.

## Contract alignment fixes

Also correct these fail-closed mismatches:

### max_executor_runs

The live Coordinator permits exactly:

max_executor_runs: 1

The publisher must reject any value other than 1 before publication.

Add a test.

### exact base SHA

The package contract uses an exact commit SHA.

Require a full 40-character hexadecimal SHA for base_sha.

Do not accept an ambiguous abbreviated SHA for publication.

Add tests for short/invalid SHA rejection.

## Preserve existing guarantees

Keep:

- runner allowlist authority;
- canonical repository-origin validation;
- deterministic target_worktree derivation;
- target main/master rejection;
- target coord/bridge namespace rejection;
- bridge coord/bridge namespace requirement;
- target remote exact-base gate;
- target-before-bridge publication ordering;
- non-force push;
- prompt round-trip through parse_next_prompt;
- unrelated-cwd CLI bootstrap protection;
- existing bridge differing content -> fail closed;
- identical bridge package -> idempotent;
- no Executor invocation from publisher;
- no systemd operations;
- no PR/merge/tag/release/deploy.

## Dirty primary checkout

The real ai-core primary checkout is intentionally allowed to already contain
unrelated dirty/untracked paths.

Publisher must neither require a clean primary checkout nor modify those paths.

The test should include dirty tracked/untracked state where practical and prove
before/after equivalence.

## Documentation

Update WORK_PACKAGE_PUBLISHER.md if implementation semantics changed,
particularly object-store behavior and resume guarantees.

Do not claim stronger byte-level guarantees than the implementation actually
proves.

## Verification

Run at minimum:

python3.10 -m pytest -q tests/test_package_publisher.py
python3.10 -m pytest -q

Also run compile/diff hygiene.

Do not start, stop, restart, enable or disable live systemd services.

At completion report:

- exact files changed;
- targeted test result;
- full-suite result;
- commit SHA;
- pushed target branch SHA;
- any remaining limitation.
