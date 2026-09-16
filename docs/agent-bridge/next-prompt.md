---
coord_version: 1
state: EXECUTOR_READY
prompt_id: architect-work-package-publisher-review-fix2-001
target_repo: kkobanenko/ai-core
target_branch: feat/003-architect-work-package-publisher-v1-20260916
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/feat-003-architect-work-package-publisher-v1-20260916
base_sha: 2cbe861bfef91d605126618eb8a0e638335a11fc
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: tools/dev_coordinator/package_publisher.py,tests/test_package_publisher.py,docs/coordination/WORK_PACKAGE_PUBLISHER.md
required_paths: tests/test_package_publisher.py
publication_commit: true
publication_push: true
commit_message: test: harden publisher real-git integration
transient_paths: uv.lock
---

# Architect Work-Package Publisher v1 — review fix 2

Continue from exact head:

2cbe861bfef91d605126618eb8a0e638335a11fc

The previous independent review did NOT find a publisher runtime failure.
It found a defect in the new real-Git integration test fixture before
publish_work_package() is called.

## Observed failure

test_real_git_integration_publish_and_idempotency fails inside
_init_local_github_clone():

    git push -u origin main

with:

    src refspec main does not match any

The temporary repository must not depend on the operator's global
init.defaultBranch configuration.

## Important second fixture problem

Do not merely fix the local branch name.

The current fixture configures a canonical-looking origin and then uses:

    url.<local-file-uri>.insteadOf=git@github.com:kkobanenko/ai-core.git

This is unsuitable for this integration test because Git's:

    git remote get-url origin

expands insteadOf mappings.

Production read_origin_repo() deliberately uses remote get-url and canonicalizes
the result. Therefore a file:// expansion can make the publisher see a
non-GitHub origin and fail the identity gate.

Do NOT weaken production origin validation merely to make the test pass.

## Required integration-test transport

Build a genuinely local, no-network real-Git test while preserving the literal
configured origin identity:

    git@github.com:kkobanenko/ai-core.git

Recommended implementation:

- create a temporary local bare repository;
- configure clone origin literally as
  git@github.com:kkobanenko/ai-core.git;
- use a temporary fake SSH transport via GIT_SSH_COMMAND (or an equally isolated
  mechanism) that maps git-upload-pack / git-receive-pack for that test origin
  to the temporary local bare repository;
- inherit this environment into the real publisher Git subprocesses;
- do not use url.*.insteadOf for the canonical origin.

The fake transport must reject unexpected host/command shapes rather than
silently routing arbitrary requests.

No network access is allowed.

## Default branch independence

The fixture must also be independent of git init.defaultBranch.

Acceptable solutions include explicitly creating/initializing main, or pushing:

    HEAD:refs/heads/main

instead of assuming that the local branch is named main.

Prefer a deterministic explicit setup and assert it.

## Mandatory assertions

The real non-dry-run integration test must actually reach
publish_work_package() and prove:

1. configured origin identity remains exactly canonical before publication;
2. target remote branch is absent initially;
3. bridge remote branch is absent initially;
4. publisher creates target branch exactly at base_sha;
5. publisher creates and successfully pushes a real bridge commit;
6. bridge commit exists in the local bare remote object database;
7. remote docs/agent-bridge/next-prompt.md exactly matches rendered prompt;
8. identical rerun is idempotent;
9. target ref does not move on identical rerun;
10. bridge ref does not move on identical rerun;
11. dirty tracked primary content remains unchanged;
12. dirty untracked primary content remains unchanged;
13. primary index remains unchanged;
14. no real github.com connection is attempted.

## Keep production fixes from fix1

Preserve:

- objects for bridge commit remain reachable through push;
- temporary GIT_INDEX_FILE;
- full 40-character base SHA requirement;
- max_executor_runs == 1;
- non-force publication;
- exact target-before-bridge ordering;
- canonical origin validation;
- prompt parser round-trip;
- idempotent bridge behavior.

Do not change production package_publisher.py unless the corrected genuine
real-Git test exposes an actual production defect.

## Verification

Run:

python3.10 -m pytest -q   tests/test_package_publisher.py::test_real_git_integration_publish_and_idempotency

python3.10 -m pytest -q tests/test_package_publisher.py

python3.10 -m pytest -q

Also run py_compile / diff hygiene.

Do not start or restart systemd services.
Do not create PRs.
Do not merge.
Do not deploy.

At completion report:
- exact files changed;
- whether production publisher code changed and why;
- real-Git integration result;
- targeted publisher result;
- full-suite result;
- commit SHA;
- pushed target SHA.
