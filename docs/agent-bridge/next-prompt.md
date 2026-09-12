---
coord_version: 1
state: EXECUTOR_READY
prompt_id: self-update-installer-import-bootstrap-012
target_repo: kkobanenko/ai-core
target_branch: fix/002-self-update-installer-import-bootstrap-20260912
target_worktree: /home/kok4444/projects/.coordinator-worktrees/ai-core/fix-002-self-update-installer-import-bootstrap-20260912
base_sha: 7b9191048e7c933d2e6f8ef9e55a1236b389ec07
hosted_ci: forbidden
max_executor_runs: 1
allowed_paths: scripts/install_dev_coordinator_runner.py, tests/test_dev_coordinator_updater_install.py
required_paths: scripts/install_dev_coordinator_runner.py, tests/test_dev_coordinator_updater_install.py
transient_paths: uv.lock
publication_commit: true
publication_push: true
commit_message: fix(coord): make installer direct invocation self-contained
---

# Task

Fix the commissioning defect discovered by the real operator bootstrap: invoking `/usr/bin/python3.10 /absolute/path/scripts/install_dev_coordinator_runner.py ...` from outside the repository fails with `ModuleNotFoundError: No module named 'tools'` before systemd activation.

Requirements:
- Keep scope strictly to installer bootstrap/import path plus its tests.
- Make direct absolute-path invocation self-contained from any current working directory, without requiring operator-provided `PYTHONPATH`.
- Prefer the smallest deterministic fix: ensure the repository root is on `sys.path` before any later local `tools.*` imports are executed.
- Do not change updater/runner behavior, systemd ordering, configs, product code, governance, or deployment scope.
- Add regression coverage that exercises the installer as a real subprocess from a directory outside the repository with `PYTHONPATH` absent; at minimum `--help` must work, and preferably a non-activating parse/config path if feasible without touching live systemd.
- No force/reset/clean/rebase/stash/pull.
- Do not commit/push manually; Coordinator owns publication.
