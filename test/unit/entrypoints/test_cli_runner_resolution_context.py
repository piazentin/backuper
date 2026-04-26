from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from backuper.commands import (
    NewCommand,
    RestoreCommand,
    UpdateCommand,
    VerifyIntegrityCommand,
)
from backuper.components.destination_lock import DestinationLockContendedError
from backuper.entrypoints.cli import runner
from backuper.models import CliUsageError

# Matches production resolver wording closely enough for pytest `match=`; do not import
# private `_RESOLUTION_GUIDANCE` from wiring.
_READ_FAILURE_STUB = "SQLite manifest: stub not ready for read"


class _RecordingDestinationLock:
    def __init__(self) -> None:
        self.acquired_destinations: list[Path] = []
        self.destination_exists_on_acquire: list[bool] = []

    @contextmanager
    def acquire(self, destination_root: Path) -> Iterator[None]:
        self.acquired_destinations.append(destination_root)
        self.destination_exists_on_acquire.append(destination_root.exists())
        yield


class _ContendedDestinationLock:
    @contextmanager
    def acquire(self, destination_root: Path) -> Iterator[None]:
        raise DestinationLockContendedError
        yield


@pytest.fixture
def _patch_write_flows(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop_new_backup(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        return None

    async def _noop_add_version(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(runner, "new_backup", _noop_new_backup)
    monkeypatch.setattr(runner, "add_version", _noop_add_version)


def test_run_new_resolves_database_with_write_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _patch_write_flows: None
) -> None:
    source = tmp_path / "src"
    destination = tmp_path / "backup"
    source.mkdir()
    (source / "a.txt").write_text("payload", encoding="utf-8")
    calls: list[str] = []

    def _fake_create_backup_database(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs["operation"])
        return object()

    monkeypatch.setattr(runner, "create_backup_database", _fake_create_backup_database)

    runner.run_new(
        NewCommand(version="v1", source=str(source), location=str(destination)),
    )

    assert calls == ["write"]


def test_run_update_resolves_database_with_write_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _patch_write_flows: None
) -> None:
    source = tmp_path / "src"
    destination = tmp_path / "backup"
    source.mkdir()
    destination.mkdir()
    (source / "a.txt").write_text("payload", encoding="utf-8")
    calls: list[str] = []

    def _fake_create_backup_database(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs["operation"])
        return object()

    monkeypatch.setattr(runner, "create_backup_database", _fake_create_backup_database)

    runner.run_update(
        UpdateCommand(version="v2", source=str(source), location=str(destination)),
    )

    assert calls == ["write"]


def test_run_new_creates_destination_before_entering_destination_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _patch_write_flows: None
) -> None:
    source = tmp_path / "src"
    destination = tmp_path / "backup"
    source.mkdir()
    (source / "a.txt").write_text("payload", encoding="utf-8")
    destination_lock = _RecordingDestinationLock()

    monkeypatch.setattr(
        runner, "create_destination_write_lock", lambda: destination_lock
    )

    runner.run_new(
        NewCommand(version="v1", source=str(source), location=str(destination)),
    )

    assert destination_lock.acquired_destinations == [destination]
    assert destination_lock.destination_exists_on_acquire == [True]


def test_run_update_maps_destination_lock_contention_to_cli_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _patch_write_flows: None
) -> None:
    source = tmp_path / "src"
    destination = tmp_path / "backup"
    source.mkdir()
    destination.mkdir()
    (source / "a.txt").write_text("payload", encoding="utf-8")

    monkeypatch.setattr(
        runner, "create_destination_write_lock", _ContendedDestinationLock
    )

    with pytest.raises(
        CliUsageError, match=r"already being modified by another active writer"
    ):
        runner.run_update(
            UpdateCommand(version="v2", source=str(source), location=str(destination)),
        )


def test_run_new_maps_destination_lock_contention_to_cli_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _patch_write_flows: None
) -> None:
    source = tmp_path / "src"
    destination = tmp_path / "backup"
    source.mkdir()
    (source / "a.txt").write_text("payload", encoding="utf-8")

    monkeypatch.setattr(
        runner, "create_destination_write_lock", _ContendedDestinationLock
    )

    with pytest.raises(
        CliUsageError, match=r"already being modified by another active writer"
    ):
        runner.run_new(
            NewCommand(version="v1", source=str(source), location=str(destination)),
        )


def test_run_restore_uses_read_operation_and_raises_actionable_guidance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup = tmp_path / "backup"
    destination = tmp_path / "restored"
    backup.mkdir()
    calls: list[str] = []

    def _fake_create_backup_database(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs["operation"])
        raise CliUsageError(_READ_FAILURE_STUB)

    monkeypatch.setattr(runner, "create_backup_database", _fake_create_backup_database)

    with pytest.raises(CliUsageError, match=r"SQLite manifest:.*not ready for read"):
        runner.run_restore(
            RestoreCommand(
                location=str(backup),
                destination=str(destination),
                version_name="v1",
            )
        )

    assert calls == ["read"]


def test_run_verify_integrity_uses_read_operation_and_raises_actionable_guidance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup = tmp_path / "backup"
    backup.mkdir()
    calls: list[str] = []

    def _fake_create_backup_database(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs["operation"])
        raise CliUsageError(_READ_FAILURE_STUB)

    monkeypatch.setattr(runner, "create_backup_database", _fake_create_backup_database)

    with pytest.raises(CliUsageError, match=r"SQLite manifest:.*not ready for read"):
        runner.run_verify_integrity(VerifyIntegrityCommand(location=str(backup)))

    assert calls == ["read"]
