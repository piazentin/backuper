from __future__ import annotations

import os
from contextlib import AbstractContextManager
from io import BufferedRandom
from pathlib import Path
from types import TracebackType

from backuper.ports import DestinationWriteLock

_LOCK_FILENAME = ".backuper.lock"


class DestinationLockContendedError(Exception):
    """Raised when another active writer already holds the destination lock."""


class _DestinationLockHandle(AbstractContextManager[None]):
    def __init__(self, lock_path: Path) -> None:
        self._lock_path = lock_path
        self._lock_file: BufferedRandom | None = None

    def __enter__(self) -> None:
        lock_path = self._lock_path
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = lock_path.open(mode="a+b")
        try:
            _acquire_non_blocking_exclusive(self._lock_file.fileno())
        except OSError as exc:
            self._lock_file.close()
            self._lock_file = None
            raise DestinationLockContendedError from exc
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._lock_file is None:
            return None
        try:
            _release(self._lock_file.fileno())
        finally:
            self._lock_file.close()
            self._lock_file = None
        return None


class LocalDestinationWriteLock(DestinationWriteLock):
    """Non-blocking exclusive lock implemented via a local lock file."""

    def acquire(self, destination_root: Path) -> AbstractContextManager[None]:
        return _DestinationLockHandle(destination_root / _LOCK_FILENAME)


if os.name == "nt":
    import msvcrt

    _locking = getattr(msvcrt, "locking")
    _lk_nblck = getattr(msvcrt, "LK_NBLCK")
    _lk_unlck = getattr(msvcrt, "LK_UNLCK")

    def _acquire_non_blocking_exclusive(fd: int) -> None:
        _locking(fd, _lk_nblck, 1)

    def _release(fd: int) -> None:
        _locking(fd, _lk_unlck, 1)
else:
    import fcntl

    def _acquire_non_blocking_exclusive(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _release(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)
