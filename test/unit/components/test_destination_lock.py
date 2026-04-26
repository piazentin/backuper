from __future__ import annotations

import errno

import pytest
from backuper.components import destination_lock
from backuper.models import DestinationLockContendedError


def test_is_lock_contention_error_for_retry_errnos() -> None:
    assert destination_lock._is_lock_contention_error(OSError(errno.EAGAIN, "busy"))
    assert destination_lock._is_lock_contention_error(
        OSError(errno.EWOULDBLOCK, "would block")
    )


def test_is_lock_contention_error_for_non_contention_errno() -> None:
    assert not destination_lock._is_lock_contention_error(
        OSError(errno.EBADF, "bad fd")
    )


def test_destination_lock_handle_re_raises_non_contention_oserror(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handle = destination_lock._DestinationLockHandle(tmp_path / ".backuper.lock")

    def _raise_non_contention(_fd: int) -> None:
        raise OSError(errno.EBADF, "bad fd")

    monkeypatch.setattr(
        destination_lock, "_acquire_non_blocking_exclusive", _raise_non_contention
    )

    with pytest.raises(OSError, match="bad fd"):
        with handle:
            pass


def test_destination_lock_handle_maps_contention_oserror(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handle = destination_lock._DestinationLockHandle(tmp_path / ".backuper.lock")

    def _raise_contention(_fd: int) -> None:
        raise OSError(errno.EAGAIN, "busy")

    monkeypatch.setattr(
        destination_lock, "_acquire_non_blocking_exclusive", _raise_contention
    )

    with pytest.raises(DestinationLockContendedError):
        with handle:
            pass
