"""Exactly-once persistent claim для logical EXECUTOR_READY identity."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tools.dev_coordinator.models import BridgePrompt
from tools.dev_coordinator.paths import ensure_state_layout


@dataclass(frozen=True)
class ClaimResult:
    """Итог попытки CLAIM."""

    acquired: bool
    claim_path: Path
    identity_key: str
    identity_hash: str
    reason: str
    existing: Optional[dict] = None


def build_task_identity(prompt: BridgePrompt) -> str:
    """Логическая identity задачи (стабильная строка).

    Минимум: prompt_id, target_repo, target_branch, base_sha, SHA256(full next-prompt).
    """
    content_hash = hashlib.sha256(prompt.raw_text.encode("utf-8")).hexdigest()
    return "|".join(
        [
            (prompt.prompt_id or "").strip(),
            (prompt.target_repo or "").strip(),
            (prompt.target_branch or "").strip(),
            (prompt.base_sha or "").strip(),
            content_hash,
        ]
    )


def identity_hash(identity_key: str) -> str:
    """Имя файла claim — SHA256 от identity_key."""
    return hashlib.sha256(identity_key.encode("utf-8")).hexdigest()


def claim_path_for(state_dir: Path, identity_key: str) -> Path:
    ensure_state_layout(state_dir)
    return state_dir / "claims" / f"{identity_hash(identity_key)}.json"


def try_acquire_claim(
    prompt: BridgePrompt,
    *,
    state_dir: Path,
    pid: Optional[int] = None,
) -> ClaimResult:
    """Атомарно создать claim (O_CREAT|O_EXCL).

    Если файл уже есть — НЕ запускать Executor (false negative / HUMAN_REQUIRED).
    Автоматический reclaim по timeout в v0.1.1 отсутствует.
    """
    ensure_state_layout(state_dir)
    key = build_task_identity(prompt)
    digest = identity_hash(key)
    path = state_dir / "claims" / f"{digest}.json"

    payload = {
        "version": 1,
        "identity_key": key,
        "identity_hash": digest,
        "prompt_id": prompt.prompt_id,
        "target_repo": prompt.target_repo,
        "target_branch": prompt.target_branch,
        "base_sha": prompt.base_sha,
        "prompt_sha256": hashlib.sha256(prompt.raw_text.encode("utf-8")).hexdigest(),
        "claimed_at_unix": time.time(),
        "pid": pid if pid is not None else os.getpid(),
        "status": "claimed",
    }

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(path), flags, 0o644)
    except FileExistsError:
        existing = _read_json(path)
        return ClaimResult(
            acquired=False,
            claim_path=path,
            identity_key=key,
            identity_hash=digest,
            reason=(
                "execution claim already exists for this EXECUTOR_READY identity; "
                "refusing second launch (no automatic reclaim in v0.1.1)"
            ),
            existing=existing,
        )

    try:
        data = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        os.write(fd, data.encode("utf-8"))
    finally:
        os.close(fd)

    return ClaimResult(
        acquired=True,
        claim_path=path,
        identity_key=key,
        identity_hash=digest,
        reason="claim acquired",
        existing=None,
    )


def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"unreadable": True, "path": str(path)}
