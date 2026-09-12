"""Каталог локального состояния Coordinator (вне git worktree)."""

from __future__ import annotations

import os
from pathlib import Path


def default_state_dir() -> Path:
    """${XDG_STATE_HOME:-~/.local/state}/ai-core-dev-coordinator/

    Можно переопределить через AI_CORE_COORDINATOR_STATE_DIR (тесты / отладка).
    """
    override = os.environ.get("AI_CORE_COORDINATOR_STATE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        base = Path(xdg).expanduser()
    else:
        base = Path.home() / ".local" / "state"
    return (base / "ai-core-dev-coordinator").resolve()


def ensure_state_layout(state_dir: Path) -> None:
    """Создать подкаталоги claims/ и locks/ при необходимости."""
    (state_dir / "claims").mkdir(parents=True, exist_ok=True)
    (state_dir / "locks").mkdir(parents=True, exist_ok=True)
