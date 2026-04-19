from __future__ import annotations

from pathlib import Path

import pytest
from backuper.commands import (
    NewCommand,
    RestoreCommand,
    UpdateCommand,
    VerifyIntegrityCommand,
)
from backuper.entrypoints.cli import runner
from backuper.entrypoints.wiring import _RESOLUTION_GUIDANCE
from backuper.models import CliUsageError


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


def test_run_restore_uses_read_operation_and_raises_actionable_guidance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup = tmp_path / "backup"
    destination = tmp_path / "restored"
    backup.mkdir()
    calls: list[str] = []

    def _fake_create_backup_database(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs["operation"])
        raise CliUsageError(_RESOLUTION_GUIDANCE)

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
        raise CliUsageError(_RESOLUTION_GUIDANCE)

    monkeypatch.setattr(runner, "create_backup_database", _fake_create_backup_database)

    with pytest.raises(CliUsageError, match=r"SQLite manifest:.*not ready for read"):
        runner.run_verify_integrity(VerifyIntegrityCommand(location=str(backup)))

    assert calls == ["read"]
