"""Локальные flock-замки (fcntl) вне git worktree."""

from __future__ import annotations

import fcntl
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, TextIO

from tools.dev_coordinator.paths import ensure_state_layout

MaintenanceMode = Literal["shared", "exclusive"]


def _open_lock_file(lock_path: Path) -> TextIO:
    """Открыть lock-файл для flock (создаёт при отсутствии, не удаляет при release)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    return open(lock_path, "a+", encoding="utf-8")


def _write_pid_best_effort(fh: TextIO) -> None:
    try:
        fh.seek(0)
        fh.truncate()
        import os

        fh.write(f"pid={os.getpid()}\n")
        fh.flush()
    except OSError:
        pass


@dataclass
class MaintenanceGateLock:
    """Maintenance gate: shared (runner) или exclusive (updater) на одном файле."""

    state_dir: Path
    mode: MaintenanceMode
    non_blocking: bool = True
    _fh: Optional[TextIO] = None

    @property
    def lock_path(self) -> Path:
        return self.state_dir / "locks" / "coordinator-maintenance.lock"

    def acquire(self) -> bool:
        ensure_state_layout(self.state_dir)
        self._fh = _open_lock_file(self.lock_path)
        flags = fcntl.LOCK_SH if self.mode == "shared" else fcntl.LOCK_EX
        if self.non_blocking:
            flags |= fcntl.LOCK_NB
        try:
            fcntl.flock(self._fh.fileno(), flags)
        except BlockingIOError:
            self._fh.close()
            self._fh = None
            return False
        _write_pid_best_effort(self._fh)
        return True

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "MaintenanceGateLock":
        if not self.acquire():
            raise RuntimeError("maintenance gate lock is held by another process")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


@dataclass
class UpdaterExclusionLock:
    """Эксклюзивный flock: только один updater oneshot за раз."""

    state_dir: Path
    non_blocking: bool = True
    _fh: Optional[TextIO] = None

    @property
    def lock_path(self) -> Path:
        return self.state_dir / "locks" / "coordinator-updater.lock"

    def acquire(self) -> bool:
        ensure_state_layout(self.state_dir)
        self._fh = _open_lock_file(self.lock_path)
        flags = fcntl.LOCK_EX
        if self.non_blocking:
            flags |= fcntl.LOCK_NB
        try:
            fcntl.flock(self._fh.fileno(), flags)
        except BlockingIOError:
            self._fh.close()
            self._fh = None
            return False
        _write_pid_best_effort(self._fh)
        return True

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "UpdaterExclusionLock":
        if not self.acquire():
            raise RuntimeError("updater exclusion lock is held by another process")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


@dataclass
class ProcessLock:
    """Эксклюзивный flock на файл в state dir.

    Держится на время одной launch-последовательности (claim + executor).
    Два Coordinator не должны одновременно запускать Executor.
    """

    state_dir: Path
    non_blocking: bool = True
    _fh: Optional[TextIO] = None

    @property
    def lock_path(self) -> Path:
        return self.state_dir / "locks" / "coordinator.lock"

    def acquire(self) -> bool:
        """Вернуть True если lock получен, False если занят (non-blocking)."""
        ensure_state_layout(self.state_dir)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        # 'a+' создаёт файл при отсутствии; не удаляем при unlock.
        self._fh = open(self.lock_path, "a+", encoding="utf-8")
        flags = fcntl.LOCK_EX
        if self.non_blocking:
            flags |= fcntl.LOCK_NB
        try:
            fcntl.flock(self._fh.fileno(), flags)
        except BlockingIOError:
            self._fh.close()
            self._fh = None
            return False
        # Запишем pid для диагностики (best-effort).
        try:
            self._fh.seek(0)
            self._fh.truncate()
            import os

            self._fh.write(f"pid={os.getpid()}\n")
            self._fh.flush()
        except OSError:
            pass
        return True

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "ProcessLock":
        if not self.acquire():
            raise RuntimeError("coordinator process lock is held by another process")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
