---
coord_version: 1
state: EXECUTOR_READY
prompt_id: architect-work-package-publisher-review-fix4-001
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
commit_message: test: complete publisher real-git harness
transient_paths: .tmp_run_checks.sh,uv.lock
---

# Architect Work-Package Publisher v1 — review fix 4

Continue from exact base:

f31c98a24c7bd875b8c2a1e29ae34e734f3e93fd

This is TEST-HARNESS-ONLY work.

You may modify exactly:

    tests/test_package_publisher.py

Do NOT modify production code, CLI, docs, Coordinator, Runner, configs, or any
other tracked path.

A previous failed attempt produced a useful diff but was intentionally discarded
after inspection. Reimplement the required solution cleanly from the exact base.

## Part A — preserve the correct fake SSH parser fix

The fake SSH script must correctly support real Git invocation where the remote
command arrives as ONE argv item after the host, for example:

    git-receive-pack 'kkobanenko/ai-core.git'

or:

    git-upload-pack 'kkobanenko/ai-core.git'

Use Python shlex.split() for that single command string.

Requirements:

- keep strict expected host:
      git@github.com
- tolerate legitimate SSH option argv before the host;
- after the host, require an explicitly supported remote-command shape;
- single-string form:
      shlex.split(...)
      exactly 2 tokens;
- optionally support already-split two-argument form, but validate it strictly;
- allow only:
      git-upload-pack
      git-receive-pack
- normalize only the expected .git suffix;
- require repository exactly:
      kkobanenko/ai-core
- reject malformed quoting;
- reject additional command tokens;
- reject wrong repository;
- reject unsupported command;
- do NOT use shell=True or invoke a shell;
- after successful validation, production-like transport still uses:
      os.execvp(validated_command, [validated_command, local_bare_path])

## Part B — fix the erroneous positive parser tests

The direct parser unit tests must NOT require a real git-upload-pack or
git-receive-pack server process to complete successfully without a Git client.

Add a TEST-ONLY validation mode to the generated fake SSH test script.

Recommended contract:

    FAKE_SSH_VALIDATE_ONLY=1

Behavior:

1. perform ALL normal validation first:
   - host;
   - argv shape;
   - shlex parsing;
   - token count;
   - allowed command;
   - exact repository;
2. write the normal invocation log;
3. if FAKE_SSH_VALIDATE_ONLY == "1":
       exit 0
   instead of os.execvp();
4. otherwise execute the real validated git-*-pack command exactly as before.

This environment variable is solely a test harness feature.

## Critical separation

Focused direct fake-SSH parser tests MAY set:

    FAKE_SSH_VALIDATE_ONLY=1

The real:

    test_real_git_integration_publish_and_idempotency

MUST NOT set or inherit validate-only mode.

The real integration path must still use actual:

    git push
    git ls-remote
    git-upload-pack / git-receive-pack

against the temporary local bare repository.

Add an explicit assertion/helper if useful proving the real integration
environment does not contain FAKE_SSH_VALIDATE_ONLY.

## Focused tests

Direct tests must prove at least:

Accepted in validate-only mode:

    git-receive-pack 'kkobanenko/ai-core.git'
    git-upload-pack 'kkobanenko/ai-core.git'

Rejected:

- wrong repository;
- unexpected command;
- extra command token;
- malformed quoting.

If the already-split argv form is retained, test it too.

The tests should verify the invocation log records the validated command.

## Mandatory real-Git integration proof

test_real_git_integration_publish_and_idempotency must be genuinely non-dry-run,
network-free, and must actually reach publish_work_package().

It must prove:

1. literal configured origin remains:
       git@github.com:kkobanenko/ai-core.git
2. target branch initially absent;
3. bridge branch initially absent;
4. publisher creates target exactly at base SHA;
5. publisher creates and pushes a real bridge commit;
6. bridge commit exists in bare remote object database;
7. next-prompt.md in remote bridge equals rendered prompt exactly;
8. identical rerun succeeds idempotently;
9. target ref does not move;
10. bridge ref does not move;
11. dirty tracked primary content is preserved;
12. dirty untracked primary content is preserved;
13. primary index is preserved;
14. fake SSH invocation log proves local transport was used;
15. no github.com network connection is required.

Do not weaken production origin validation or publisher behavior to make tests
green.

## Production code invariant

The following MUST remain byte-identical to base:

    tools/dev_coordinator/package_publisher.py
    scripts/publish_dev_coordinator_package.py

No production fix is authorized by this package.

## Executor hygiene

Prefer running verification commands directly.

Do not create helper shell files.

If .tmp_run_checks.sh is created for any reason, it is declared as an exact
transient path but MUST be removed before completion if shell access permits.

Do not create arbitrary temp files under repository root.

## Verification

Run, in this order:

    python3.10 -m py_compile tests/test_package_publisher.py

    python3.10 -m pytest -q       tests/test_package_publisher.py -k 'fake_ssh'

    python3.10 -m pytest -q       tests/test_package_publisher.py::test_real_git_integration_publish_and_idempotency

    python3.10 -m pytest -q tests/test_package_publisher.py

    python3.10 -m pytest -q

Then verify:

    git status --short
    git diff --name-only f31c98a24c7bd875b8c2a1e29ae34e734f3e93fd

Final tracked diff must contain exactly:

    tests/test_package_publisher.py

Do not restart services.
Do not create a PR.
Do not merge.
Do not deploy.

Report:

- exact changed paths;
- fake SSH focused result;
- real-Git integration result;
- publisher suite result;
- full suite result;
- confirmation production publisher/CLI unchanged;
- commit SHA;
- pushed target SHA.
