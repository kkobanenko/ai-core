---
coord_version: 1
state: EXECUTOR_READY
prompt_id: architect-work-package-publisher-review-fix3-001
target_repo: kkobanenko/ai-core
target_branch: feat/003-architect-work-package-publisher-v1-20260916
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/feat-003-architect-work-package-publisher-v1-20260916
base_sha: f31c98a24c7bd875b8c2a1e29ae34e734f3e93fd
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: tests/test_package_publisher.py
required_paths: tests/test_package_publisher.py
publication_commit: true
publication_push: true
commit_message: test: fix publisher fake ssh command parsing
transient_paths: uv.lock
---

# Architect Work-Package Publisher v1 — review fix 3

Continue from exact head:

f31c98a24c7bd875b8c2a1e29ae34e734f3e93fd

This is a TEST-HARNESS-ONLY fix.

You may modify exactly:

tests/test_package_publisher.py

Do NOT modify:

- tools/dev_coordinator/package_publisher.py
- scripts/publish_dev_coordinator_package.py
- docs/**
- Runner or Coordinator code

## Confirmed failure

The exact-head real-Git integration test fails before publish_work_package()
is called.

Observed stderr:

    fake-ssh: insufficient args after host:
    ["git-receive-pack 'kkobanenko/ai-core.git'"]

Git invokes GIT_SSH_COMMAND with the remote server command as one argument after
the host, for example:

    git@github.com
    "git-receive-pack 'kkobanenko/ai-core.git'"

The current fake SSH fixture incorrectly expects two separate argv entries:

    command
    repo

## Required fix

Correct the fake SSH test transport to parse the real Git SSH invocation.

Preferred behavior:

1. Preserve the existing strict host validation.
2. Preserve tolerance for legitimate ssh options appearing before the host.
3. After locating the expected host, require the expected remote command shape.
4. Parse the single command-string safely using Python shlex.split.
5. Require exactly two parsed tokens:
   - command
   - repository path
6. Allow only:
   - git-upload-pack
   - git-receive-pack
7. Require the repository to normalize exactly to:
   kkobanenko/ai-core
8. Reject unexpected hosts, commands, repositories, malformed quoting, or extra
   command tokens.
9. Do not invoke a shell to execute the parsed command.
10. Continue using os.execvp with the validated command and local bare path.

If the local Git version legitimately supplies an equivalent already-split form,
support it only with explicit validation and tests. Do not broadly join arbitrary
argv into a shell command.

## Add focused fake-SSH tests

Add direct tests proving at minimum:

- accepted:
  git-receive-pack 'kkobanenko/ai-core.git'

- accepted:
  git-upload-pack 'kkobanenko/ai-core.git'

- rejected wrong repository;
- rejected unexpected command;
- rejected additional command tokens;
- rejected malformed command string.

Tests must remain local-only and network-free.

## Mandatory real-Git proof

After fixing the parser, the existing:

test_real_git_integration_publish_and_idempotency

must progress past fixture setup and actually call the real
publish_work_package() non-dry-run.

It must prove the already-defined properties:

- canonical literal GitHub origin preserved;
- target absent -> created at exact base SHA;
- bridge absent -> real bridge commit pushed;
- bridge commit readable from bare remote;
- exact next-prompt content;
- identical rerun idempotent;
- dirty tracked content preserved;
- dirty untracked content preserved;
- primary index preserved;
- no network GitHub access.

Do not weaken any assertion merely to obtain green tests.

## Production contract

Do not modify production publisher code in this package.

The object-store fix, full-SHA gate, max_executor_runs == 1 gate, publication
ordering, canonical origin validation, non-force push and idempotency from fix1
must remain unchanged.

## Verification

Run:

python3.10 -m pytest -q   tests/test_package_publisher.py::test_real_git_integration_publish_and_idempotency

python3.10 -m pytest -q tests/test_package_publisher.py

python3.10 -m pytest -q

Also run py_compile and git diff/status hygiene.

Do not start/restart systemd.
Do not create a PR.
Do not merge.
Do not deploy.

At completion report:

- exact files changed;
- confirmation production publisher code is unchanged;
- real-Git integration result;
- publisher suite result;
- full-suite result;
- commit SHA;
- pushed target SHA.
