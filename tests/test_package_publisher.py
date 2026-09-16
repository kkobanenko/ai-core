"""Тесты Architect work-package publisher (без live GitHub / systemd)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Mapping

import pytest

from tools.dev_coordinator.managed_worktrees import derive_executor_worktree_path
from tools.dev_coordinator.parse import parse_next_prompt
from tools.dev_coordinator.package_publisher import (
    WorkPackageSpec,
    _assert_git_command_allowed,
    _FORBIDDEN_GIT_PREFIXES,
    publish_work_package,
    read_checkout_snapshot,
    render_next_prompt,
    resolve_bridge_branch,
    snapshots_equal,
)
from tools.dev_coordinator.runner_config import parse_runner_config

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PUBLISH_SCRIPT = _REPO_ROOT / "scripts" / "publish_dev_coordinator_package.py"

_CANONICAL_GITHUB_ORIGIN = "git@github.com:kkobanenko/ai-core.git"
_MAIN_REF = "refs/heads/main"

_BASE_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_BRIDGE_SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
_OTHER_SHA = "cccccccccccccccccccccccccccccccccccccccc"


def _make_runner_config(tmp_path: Path, clone: Path) -> Path:
    """Записать минимальный runner.json для тестов."""
    coord = tmp_path / "coord"
    managed = tmp_path / "worktrees"
    agent = tmp_path / "agent"
    for d in (coord, managed, clone):
        d.mkdir(parents=True, exist_ok=True)
    agent.write_text("#!/bin/sh\n", encoding="utf-8")
    agent.chmod(0o755)
    cfg_path = tmp_path / "runner.json"
    cfg_path.write_text(
        json.dumps(
            {
                "poll_interval_seconds": 15,
                "coordinator_repo_root": str(coord),
                "managed_worktree_root": str(managed),
                "agent_bin": str(agent),
                "bridge_prefix": "coord/bridge/",
                "repositories": {
                    "kkobanenko/ai-core": str(clone),
                },
            }
        ),
        encoding="utf-8",
    )
    return cfg_path


def _base_spec(
    tmp_path: Path,
    clone: Path,
    *,
    dry_run: bool = False,
    target_branch: str = "feat/test-pkg",
    bridge_branch: str = "coord/bridge/test-pkg",
    base_sha: str = _BASE_SHA,
) -> WorkPackageSpec:
    (clone / ".git").mkdir(parents=True, exist_ok=True)
    cfg = _make_runner_config(tmp_path, clone)
    config = parse_runner_config(json.loads(cfg.read_text()))
    wt = derive_executor_worktree_path(
        config.managed_worktree_root, "kkobanenko/ai-core", target_branch
    )
    return WorkPackageSpec(
        runner_config_path=cfg,
        bridge_repo="kkobanenko/ai-core",
        target_repo="kkobanenko/ai-core",
        base_sha=base_sha,
        target_branch=target_branch,
        bridge_branch=bridge_branch,
        prompt_id="test-pkg-001",
        allowed_paths=("foo.py",),
        required_paths=("foo.py",),
        transient_paths=(),
        commit_message="feat: test package",
        hosted_ci="forbidden",
        publication_commit=True,
        publication_push=True,
        max_executor_runs=1,
        instruction_body="# Task\n\nDo work.\n",
        dry_run=dry_run,
    )


class FakeRemoteState:
    """In-memory симуляция remote refs для injected git runner."""

    def __init__(self) -> None:
        self.refs: dict[str, str] = {}
        self.objects: dict[str, str] = {}
        self.commands: list[tuple[list[str], str]] = []
        self.head = _BASE_SHA
        self.origin = "git@github.com:kkobanenko/ai-core.git"
        self.dirty_status = ""

    def runner(self, args, cwd):
        cmd = list(args)
        self.commands.append((cmd, str(cwd)))
        if cmd[:3] == ["remote", "get-url", "origin"]:
            return 0, self.origin + "\n", ""
        if cmd[:2] == ["ls-remote", "origin"] and len(cmd) >= 3:
            ref = cmd[2]
            branch = ref.replace("refs/heads/", "")
            sha = self.refs.get(branch)
            if sha:
                return 0, f"{sha}\t{ref}\n", ""
            return 0, "", ""
        if cmd[:2] == ["cat-file", "-e"]:
            spec = cmd[2]
            sha = spec.replace("^{commit}", "")
            if sha in (self.head, _BASE_SHA, _BRIDGE_SHA, _OTHER_SHA):
                return 0, "", ""
            return 1, "", "not found"
        if cmd[:2] == ["rev-parse", "HEAD"]:
            return 0, self.head + "\n", ""
        if cmd[:2] == ["rev-parse", "--is-inside-work-tree"]:
            return 0, "true\n", ""
        if cmd[:2] == ["branch", "--show-current"]:
            return 0, "main\n", ""
        if cmd[:2] == ["status", "--porcelain"]:
            return 0, self.dirty_status, ""
        if cmd[:2] == ["diff", "--cached", "--stat"]:
            return 0, "", ""
        if cmd[0] == "show":
            # show <sha>:path
            spec = cmd[1]
            sha, path = spec.split(":", 1)
            key = f"{sha}:{path}"
            if key in self.objects:
                return 0, self.objects[key], ""
            return 1, "", "missing"
        if cmd[:2] == ["push", "origin"]:
            refspec = cmd[2]
            if ":" not in refspec:
                return 1, "", "invalid refspec"
            src, dst = refspec.split(":", 1)
            branch = dst.replace("refs/heads/", "")
            self.refs[branch] = src
            return 0, "", ""
        if cmd[:2] == ["hash-object", "-w"]:
            blob_sha = "dddddddddddddddddddddddddddddddddddddddd"
            return 0, blob_sha + "\n", ""
        # commit-tree plumbing: делегируем минимально для injected transport
        if cmd[0] == "read-tree":
            return 0, "", ""
        if cmd[0] == "update-index":
            return 0, "", ""
        if cmd[0] == "write-tree":
            return 0, "tree0001\n", ""
        if cmd[0] == "commit-tree":
            new_sha = _BRIDGE_SHA if _BRIDGE_SHA not in self.refs.values() else _OTHER_SHA
            return 0, new_sha + "\n", ""
        return 1, "", f"unexpected: {cmd}"


def test_prompt_rendering_parses_with_parse_next_prompt(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    config = parse_runner_config(json.loads(spec.runner_config_path.read_text()))
    wt = derive_executor_worktree_path(
        config.managed_worktree_root, spec.target_repo, spec.target_branch
    )
    text = render_next_prompt(spec=spec, target_worktree=wt)
    parsed = parse_next_prompt(text)
    assert parsed.parse_error is None
    assert parsed.state is not None
    assert parsed.state.value == "EXECUTOR_READY"
    assert parsed.prompt_id == spec.prompt_id
    assert parsed.target_worktree == str(wt)


def test_deterministic_target_worktree_derivation(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone, target_branch="feat/my-feature")
    config = parse_runner_config(json.loads(spec.runner_config_path.read_text()))
    expected = derive_executor_worktree_path(
        config.managed_worktree_root, "kkobanenko/ai-core", "feat/my-feature"
    )
    text = render_next_prompt(spec=spec, target_worktree=expected)
    parsed = parse_next_prompt(text)
    assert parsed.target_worktree == str(expected)


def test_resolve_bridge_branch_from_package_id() -> None:
    assert resolve_bridge_branch(bridge_branch=None, package_id="pkg-001") == (
        "coord/bridge/pkg-001"
    )


def test_bridge_outside_namespace_fail_closed(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone, bridge_branch="feat/not-bridge")
    remote = FakeRemoteState()
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert not outcome.ok
    assert any("outside namespace" in e for e in outcome.errors)


def test_target_wrong_sha_fail_closed(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    remote = FakeRemoteState()
    remote.refs[spec.target_branch] = _OTHER_SHA
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert not outcome.ok
    assert any("target remote SHA mismatch" in e for e in outcome.errors)


def test_target_branch_absent_creates_at_base(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    remote = FakeRemoteState()
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert outcome.ok
    assert remote.refs[spec.target_branch] == _BASE_SHA
    assert outcome.bridge_remote_sha is not None


def test_target_exact_base_resumable(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    remote = FakeRemoteState()
    remote.refs[spec.target_branch] = _BASE_SHA
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert outcome.ok
    assert outcome.resumed_target


def test_existing_bridge_differing_package_fail_closed(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    remote = FakeRemoteState()
    remote.refs[spec.target_branch] = _BASE_SHA
    remote.refs[spec.bridge_branch] = _BRIDGE_SHA
    remote.objects[f"{_BRIDGE_SHA}:docs/agent-bridge/next-prompt.md"] = (
        "---\nstate: WAIT\n---\n"
    )
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert not outcome.ok
    assert any("differs" in e for e in outcome.errors)


def test_identical_package_rerun_idempotent(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    remote = FakeRemoteState()
    remote.refs[spec.target_branch] = _BASE_SHA
    config = parse_runner_config(json.loads(spec.runner_config_path.read_text()))
    wt = derive_executor_worktree_path(
        config.managed_worktree_root, spec.target_repo, spec.target_branch
    )
    prompt = render_next_prompt(spec=spec, target_worktree=wt)
    remote.refs[spec.bridge_branch] = _BRIDGE_SHA
    remote.objects[f"{_BRIDGE_SHA}:docs/agent-bridge/next-prompt.md"] = prompt

    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert outcome.ok
    assert outcome.resumed_bridge
    push_cmds = [c for c, _ in remote.commands if c[:2] == ["push", "origin"]]
    assert push_cmds == []


def _write_fake_github_ssh_script(tmp_path: Path) -> Path:
    """Локальный fake SSH: только git@github.com/kkobanenko/ai-core -> bare repo."""
    script = tmp_path / "fake-github-ssh.py"
    script.write_text(
        """#!/usr/bin/env python3
import os
import shlex
import sys

EXPECTED_HOST = "git@github.com"
EXPECTED_REPO = "kkobanenko/ai-core"
ALLOWED_CMDS = frozenset({"git-upload-pack", "git-receive-pack"})

def _fail(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)

args = sys.argv[1:]
try:
    host_idx = args.index(EXPECTED_HOST)
except ValueError:
    _fail(f"fake-ssh: unexpected invocation (no {EXPECTED_HOST}): {args!r}")

rest = args[host_idx + 1 :]
if not rest:
    _fail(f"fake-ssh: insufficient args after host: {rest!r}")

if len(rest) == 1:
    try:
        tokens = shlex.split(rest[0])
    except ValueError as exc:
        _fail(f"fake-ssh: malformed quoting in remote command: {exc}")
elif len(rest) == 2:
    tokens = list(rest)
else:
    _fail(f"fake-ssh: unexpected argv shape after host: {rest!r}")

if len(tokens) != 2:
    _fail(f"fake-ssh: expected exactly 2 tokens in remote command, got {len(tokens)}: {tokens!r}")

cmd, repo_raw = tokens
repo = repo_raw.strip("'\\"")
repo_norm = repo[:-4] if repo.endswith(".git") else repo
if repo_norm != EXPECTED_REPO:
    _fail(f"fake-ssh: unexpected repo: {repo!r}")

if cmd not in ALLOWED_CMDS:
    _fail(f"fake-ssh: unexpected command: {cmd!r}")

bare = os.environ.get("FAKE_GIT_BARE_REPO")
if not bare:
    _fail("fake-ssh: FAKE_GIT_BARE_REPO is not set")

invocation_log = os.environ.get("FAKE_SSH_INVOCATION_LOG")
if invocation_log:
    with open(invocation_log, "a", encoding="utf-8") as handle:
        handle.write(f"{cmd}\\n")

if os.environ.get("FAKE_SSH_VALIDATE_ONLY") == "1":
    sys.exit(0)

os.execvp(cmd, [cmd, bare])
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _fake_ssh_env(
    bare: Path,
    script: Path,
    invocation_log: Path,
) -> dict[str, str]:
    """Env для subprocess/git: fake SSH transport без url.insteadOf."""
    return {
        "GIT_SSH_COMMAND": str(script),
        "FAKE_GIT_BARE_REPO": str(bare.resolve()),
        "FAKE_SSH_INVOCATION_LOG": str(invocation_log),
    }


def _run_git(
    args: list[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """git subprocess с опциональным env (наследует os.environ)."""
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        env=merged,
    )


def _push_head_to_main(
    clone: Path,
    *,
    env: Mapping[str, str] | None = None,
) -> None:
    """Push текущего HEAD в refs/heads/main без зависимости от defaultBranch."""
    _run_git(
        ["push", "-u", "origin", f"HEAD:{_MAIN_REF}"],
        cwd=clone,
        env=env,
    )


def _assert_origin_canonical(clone: Path) -> None:
    """origin get-url должен оставаться literal GitHub SSH (без insteadOf)."""
    proc = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=clone,
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip() == _CANONICAL_GITHUB_ORIGIN


def _init_clone_with_origin(tmp_path: Path) -> tuple[Path, str, dict[str, str]]:
    """Bare remote + clone с canonical GitHub origin и fake SSH transport."""
    bare = tmp_path / "remote.git"
    clone = tmp_path / "clone"
    script = _write_fake_github_ssh_script(tmp_path)
    ssh_log = tmp_path / "ssh-invocations.log"
    git_env = _fake_ssh_env(bare, script, ssh_log)

    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    subprocess.run(
        ["git", "clone", str(bare), str(clone)],
        check=True,
        capture_output=True,
    )
    _run_git(
        ["remote", "set-url", "origin", _CANONICAL_GITHUB_ORIGIN],
        cwd=clone,
    )
    (clone / "README.md").write_text("init\n", encoding="utf-8")
    _run_git(["add", "README.md"], cwd=clone)
    _run_git(["commit", "-m", "init"], cwd=clone)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=clone,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    _push_head_to_main(clone, env=git_env)
    _assert_origin_canonical(clone)
    return clone, head, git_env


def _apply_git_env(monkeypatch: pytest.MonkeyPatch, git_env: dict[str, str]) -> None:
    """Пробросить fake SSH env в subprocess publisher."""
    for key, value in git_env.items():
        monkeypatch.setenv(key, value)


def test_fake_ssh_parser_accepted(tmp_path: Path) -> None:
    """Fake SSH parser принимает допустимые команды в режиме FAKE_SSH_VALIDATE_ONLY=1."""
    script = _write_fake_github_ssh_script(tmp_path)
    bare = tmp_path / "bare.git"
    bare.mkdir()
    log = tmp_path / "invocations.log"
    base_env = {
        **os.environ,
        "FAKE_GIT_BARE_REPO": str(bare),
        "FAKE_SSH_INVOCATION_LOG": str(log),
        "FAKE_SSH_VALIDATE_ONLY": "1",
    }

    # 1. Single string form git-receive-pack
    res = subprocess.run(
        [sys.executable, str(script), "git@github.com", "git-receive-pack 'kkobanenko/ai-core.git'"],
        capture_output=True,
        text=True,
        env=base_env,
    )
    assert res.returncode == 0, res.stderr

    # 2. Single string form git-upload-pack without .git suffix
    res = subprocess.run(
        [sys.executable, str(script), "git@github.com", "git-upload-pack 'kkobanenko/ai-core'"],
        capture_output=True,
        text=True,
        env=base_env,
    )
    assert res.returncode == 0, res.stderr

    # 3. Two-token argv form
    res = subprocess.run(
        [sys.executable, str(script), "git@github.com", "git-receive-pack", "kkobanenko/ai-core.git"],
        capture_output=True,
        text=True,
        env=base_env,
    )
    assert res.returncode == 0, res.stderr

    # 4. SSH options before host
    res = subprocess.run(
        [
            sys.executable,
            str(script),
            "-o",
            "BatchMode=yes",
            "-p",
            "22",
            "git@github.com",
            "git-upload-pack 'kkobanenko/ai-core.git'",
        ],
        capture_output=True,
        text=True,
        env=base_env,
    )
    assert res.returncode == 0, res.stderr

    # Проверка журнала вызовов
    recorded = log.read_text(encoding="utf-8").splitlines()
    assert recorded == [
        "git-receive-pack",
        "git-upload-pack",
        "git-receive-pack",
        "git-upload-pack",
    ]


def test_fake_ssh_parser_rejected(tmp_path: Path) -> None:
    """Fake SSH parser отклоняет некорректные репозитории, команды, кавычки и токены."""
    script = _write_fake_github_ssh_script(tmp_path)
    bare = tmp_path / "bare.git"
    bare.mkdir()
    log = tmp_path / "invocations.log"
    base_env = {
        **os.environ,
        "FAKE_GIT_BARE_REPO": str(bare),
        "FAKE_SSH_INVOCATION_LOG": str(log),
        "FAKE_SSH_VALIDATE_ONLY": "1",
    }

    # Неверный репозиторий
    res = subprocess.run(
        [sys.executable, str(script), "git@github.com", "git-receive-pack 'kkobanenko/other-repo.git'"],
        capture_output=True,
        text=True,
        env=base_env,
    )
    assert res.returncode != 0
    assert "unexpected repo" in res.stderr

    # Неразрешенная команда
    res = subprocess.run(
        [sys.executable, str(script), "git@github.com", "git-other-pack 'kkobanenko/ai-core.git'"],
        capture_output=True,
        text=True,
        env=base_env,
    )
    assert res.returncode != 0
    assert "unexpected command" in res.stderr

    # Лишний токен
    res = subprocess.run(
        [sys.executable, str(script), "git@github.com", "git-receive-pack 'kkobanenko/ai-core.git' extra"],
        capture_output=True,
        text=True,
        env=base_env,
    )
    assert res.returncode != 0
    assert "expected exactly 2 tokens" in res.stderr

    # Некорректные кавычки (malformed quoting)
    res = subprocess.run(
        [sys.executable, str(script), "git@github.com", "git-receive-pack 'kkobanenko/ai-core.git"],
        capture_output=True,
        text=True,
        env=base_env,
    )
    assert res.returncode != 0
    assert "malformed quoting" in res.stderr

    # Неверный хост
    res = subprocess.run(
        [sys.executable, str(script), "other@github.com", "git-receive-pack 'kkobanenko/ai-core.git'"],
        capture_output=True,
        text=True,
        env=base_env,
    )
    assert res.returncode != 0
    assert "unexpected invocation" in res.stderr

    # Отсутствует FAKE_GIT_BARE_REPO
    no_bare_env = dict(base_env)
    del no_bare_env["FAKE_GIT_BARE_REPO"]
    res = subprocess.run(
        [sys.executable, str(script), "git@github.com", "git-receive-pack 'kkobanenko/ai-core.git'"],
        capture_output=True,
        text=True,
        env=no_bare_env,
    )
    assert res.returncode != 0
    assert "FAKE_GIT_BARE_REPO is not set" in res.stderr


def test_dry_run_no_push_commands(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone, dry_run=True)
    remote = FakeRemoteState()
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert outcome.ok
    assert outcome.dry_run
    assert not any(c[0] == "push" for c, _ in remote.commands)


def test_forbidden_git_commands_rejected() -> None:
    with pytest.raises(ValueError, match="forbidden"):
        _assert_git_command_allowed(("reset", "--hard", "HEAD"))
    with pytest.raises(ValueError, match="forbidden"):
        _assert_git_command_allowed(("push", "--force", "origin", "refs/heads/x"))
    with pytest.raises(ValueError, match="forbidden"):
        _assert_git_command_allowed(("push", "-f", "origin", "refs/heads/x"))
    with pytest.raises(ValueError, match="forbidden"):
        _assert_git_command_allowed(("push", "--force-with-lease", "origin", "refs/heads/x"))


def test_dirty_primary_checkout_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Реальный git: dirty clone остаётся неизменным после dry-run."""
    clone, head, git_env = _init_clone_with_origin(tmp_path)
    _apply_git_env(monkeypatch, git_env)
    dirty_file = clone / "dirty.txt"
    dirty_file.write_text("changed\n", encoding="utf-8")

    spec = _base_spec(tmp_path, clone, dry_run=True, base_sha=head)
    before = read_checkout_snapshot(clone, _real_git_session())
    outcome = publish_work_package(spec)
    after = read_checkout_snapshot(clone, _real_git_session())
    assert outcome.ok
    assert snapshots_equal(before, after)
    assert "changed" in dirty_file.read_text()


def test_dry_run_mutation_boundary(tmp_path: Path) -> None:
    """Dry-run не меняет refs remote (ls-remote до/после через fake)."""
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone, dry_run=True)
    remote = FakeRemoteState()
    refs_before = dict(remote.refs)
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert outcome.ok
    assert remote.refs == refs_before


def test_cli_unrelated_cwd_bootstrap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Запуск из чужого cwd не подхватывает локальный tools/."""
    shadow = tmp_path / "shadow_project"
    shadow.mkdir()
    (shadow / "tools").mkdir()
    (shadow / "tools" / "dev_coordinator").mkdir(parents=True)
    (shadow / "tools" / "dev_coordinator" / "__init__.py").write_text(
        "raise ImportError('shadow')\n",
        encoding="utf-8",
    )
    instr = tmp_path / "task.md"
    instr.write_text("# Task\n", encoding="utf-8")
    clone, head, git_env = _init_clone_with_origin(tmp_path)
    cfg = _make_runner_config(tmp_path, clone)

    cli_env = os.environ.copy()
    cli_env.update(git_env)
    proc = subprocess.run(
        [
            sys.executable,
            str(_PUBLISH_SCRIPT),
            "--runner-config",
            str(cfg),
            "--bridge-repo",
            "kkobanenko/ai-core",
            "--target-repo",
            "kkobanenko/ai-core",
            "--base-sha",
            head,
            "--target-branch",
            "feat/cli-test",
            "--package-id",
            "cli-test",
            "--prompt-id",
            "cli-001",
            "--allowed-paths",
            "a.py",
            "--required-paths",
            "a.py",
            "--commit-message",
            "test",
            "--instruction-file",
            str(instr),
            "--dry-run",
        ],
        cwd=str(shadow),
        capture_output=True,
        text=True,
        env=cli_env,
    )
    assert "shadow" not in (proc.stderr or "")
    assert proc.returncode in (0, 1)


def _real_git_session():
    from tools.dev_coordinator.package_publisher import _GitSession
    from tools.dev_coordinator.gitutil import default_git_runner

    return _GitSession(git_runner=default_git_runner)


def test_publish_never_issues_forbidden_git_commands(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    remote = FakeRemoteState()
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert outcome.ok
    forbidden_starts = {f[0] for f in _FORBIDDEN_GIT_PREFIXES}
    for cmd in outcome.git_commands:
        assert cmd[0] not in forbidden_starts
        if cmd[0] == "push":
            assert "--force" not in cmd
            assert "-f" not in cmd


def test_target_main_rejected(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone, target_branch="main")
    remote = FakeRemoteState()
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert not outcome.ok
    assert any("forbidden target branch" in e for e in outcome.errors)


def test_max_executor_runs_must_be_one(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    bad = replace(spec, max_executor_runs=2)
    remote = FakeRemoteState()
    outcome = publish_work_package(bad, git_runner=remote.runner)
    assert not outcome.ok
    assert any("max_executor_runs must be exactly 1" in e for e in outcome.errors)


def test_base_sha_short_rejected(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone, base_sha="abc1234")
    remote = FakeRemoteState()
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert not outcome.ok
    assert any("40-character" in e for e in outcome.errors)


def test_base_sha_invalid_chars_rejected(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(
        tmp_path,
        clone,
        base_sha="g" * 40,
    )
    remote = FakeRemoteState()
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert not outcome.ok
    assert any("invalid git SHA" in e for e in outcome.errors)


def test_injected_runner_receives_plumbing_commands(tmp_path: Path) -> None:
    """Plumbing commit-tree идёт через injected runner, не мимо него."""
    clone = tmp_path / "clone"
    clone.mkdir()
    spec = _base_spec(tmp_path, clone)
    remote = FakeRemoteState()
    outcome = publish_work_package(spec, git_runner=remote.runner)
    assert outcome.ok
    plumbing = {"hash-object", "read-tree", "update-index", "write-tree", "commit-tree"}
    executed = {cmd[0] for cmd, _ in remote.commands}
    assert plumbing <= executed


def _git_ls_remote(bare: Path, branch: str) -> str | None:
    proc = subprocess.run(
        ["git", "ls-remote", str(bare), f"refs/heads/{branch}"],
        capture_output=True,
        text=True,
        check=False,
    )
    line = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else ""
    if not line:
        return None
    return line.split()[0]


def _git_show_file(bare: Path, sha: str, path: str) -> str:
    proc = subprocess.run(
        ["git", "--git-dir", str(bare), "show", f"{sha}:{path}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


def _init_local_github_clone(
    tmp_path: Path,
) -> tuple[Path, Path, str, dict[str, str], Path]:
    """Bare remote + clone: literal GitHub origin + fake SSH (без insteadOf)."""
    bare = tmp_path / "remote.git"
    clone = tmp_path / "clone"
    script = _write_fake_github_ssh_script(tmp_path)
    ssh_log = tmp_path / "ssh-invocations.log"
    git_env = _fake_ssh_env(bare, script, ssh_log)

    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    subprocess.run(
        ["git", "clone", str(bare), str(clone)],
        check=True,
        capture_output=True,
    )
    _run_git(
        ["remote", "set-url", "origin", _CANONICAL_GITHUB_ORIGIN],
        cwd=clone,
    )
    (clone / "README.md").write_text("init\n", encoding="utf-8")
    _run_git(["add", "README.md"], cwd=clone)
    _run_git(["commit", "-m", "init"], cwd=clone)
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=clone,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    _push_head_to_main(clone, env=git_env)
    _assert_origin_canonical(clone)
    assert _git_ls_remote(bare, "main") == base_sha
    return bare, clone, base_sha, git_env, ssh_log


def test_real_git_integration_publish_and_idempotency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-dry-run: real git, fake SSH transport, canonical GitHub origin."""
    assert os.environ.get("FAKE_SSH_VALIDATE_ONLY") is None
    bare, clone, base_sha, git_env, ssh_log = _init_local_github_clone(tmp_path)
    assert "FAKE_SSH_VALIDATE_ONLY" not in git_env
    target_branch = "feat/integration-pkg"
    bridge_branch = "coord/bridge/integration-pkg"

    _apply_git_env(monkeypatch, git_env)

    # (1) configured origin identity remains exactly canonical before publication.
    _assert_origin_canonical(clone)

    # (2) target remote branch absent initially; (3) bridge remote branch absent.
    assert _git_ls_remote(bare, target_branch) is None
    assert _git_ls_remote(bare, bridge_branch) is None

    # Dirty primary checkout: tracked modification + untracked file.
    readme = clone / "README.md"
    readme.write_text("init\nmodified\n", encoding="utf-8")
    untracked = clone / "untracked-dirty.txt"
    untracked.write_text("leave me\n", encoding="utf-8")

    spec = _base_spec(
        tmp_path,
        clone,
        dry_run=False,
        target_branch=target_branch,
        bridge_branch=bridge_branch,
        base_sha=base_sha,
    )
    config = parse_runner_config(json.loads(spec.runner_config_path.read_text()))
    expected_prompt = render_next_prompt(
        spec=spec,
        target_worktree=derive_executor_worktree_path(
            config.managed_worktree_root, spec.target_repo, spec.target_branch
        ),
    )

    before = read_checkout_snapshot(clone, _real_git_session())
    index_before = subprocess.run(
        ["git", "ls-files", "--stage"],
        cwd=clone,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    ssh_invocations_before = ssh_log.read_text(encoding="utf-8") if ssh_log.exists() else ""

    outcome1 = publish_work_package(spec)
    assert outcome1.ok, outcome1.errors
    assert outcome1.reason == "published"
    assert not outcome1.resumed_bridge

    # (4) publisher creates target branch exactly at base_sha.
    target_sha = _git_ls_remote(bare, target_branch)
    assert target_sha == base_sha

    # (5) publisher creates and successfully pushes a real bridge commit.
    bridge_sha = _git_ls_remote(bare, bridge_branch)
    assert bridge_sha is not None
    assert bridge_sha == outcome1.bridge_remote_sha

    # (6) bridge commit exists in the local bare remote object database.
    subprocess.run(
        ["git", "--git-dir", str(bare), "cat-file", "-e", f"{bridge_sha}^{{commit}}"],
        check=True,
        capture_output=True,
    )

    # (7) remote docs/agent-bridge/next-prompt.md exactly matches rendered prompt.
    remote_prompt = _git_show_file(
        bare, bridge_sha, "docs/agent-bridge/next-prompt.md"
    )
    assert remote_prompt == expected_prompt

    # (11–13) dirty tracked/untracked content and index unchanged after first run.
    after1 = read_checkout_snapshot(clone, _real_git_session())
    assert snapshots_equal(before, after1)
    index_after1 = subprocess.run(
        ["git", "ls-files", "--stage"],
        cwd=clone,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert index_after1 == index_before
    assert readme.read_text() == "init\nmodified\n"
    assert untracked.read_text() == "leave me\n"

    # (14) no real github.com connection: only fake SSH script was used.
    ssh_invocations_after_first = ssh_log.read_text(encoding="utf-8")
    assert ssh_invocations_after_first != ssh_invocations_before
    assert "git-receive-pack" in ssh_invocations_after_first
    assert "git-upload-pack" in ssh_invocations_after_first

    receive_pack_count_after_first = ssh_invocations_after_first.count(
        "git-receive-pack"
    )

    # (8) identical rerun is idempotent.
    outcome2 = publish_work_package(spec)
    assert outcome2.ok
    assert outcome2.resumed_bridge

    # (9–10) target and bridge refs do not move on identical rerun.
    assert _git_ls_remote(bare, target_branch) == target_sha
    assert _git_ls_remote(bare, bridge_branch) == bridge_sha
    ssh_invocations_after_second = ssh_log.read_text(encoding="utf-8")
    assert ssh_invocations_after_second.count("git-receive-pack") == (
        receive_pack_count_after_first
    )

    after2 = read_checkout_snapshot(clone, _real_git_session())
    assert snapshots_equal(before, after2)
    index_after2 = subprocess.run(
        ["git", "ls-files", "--stage"],
        cwd=clone,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert index_after2 == index_before
