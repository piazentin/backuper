"""Integration tests for CLI backend resolution behavior."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from backuper.commands import (
    NewCommand,
    RestoreCommand,
    UpdateCommand,
    VerifyIntegrityCommand,
)
from backuper.config import SqliteDbConfig
from backuper.entrypoints.cli import (
    run_new,
    run_restore,
    run_update,
    run_verify_integrity,
)
from backuper.models import CliUsageError


def _sqlite_manifest_path(backup_root: Path) -> Path:
    cfg = SqliteDbConfig(backup_dir=str(backup_root))
    return backup_root / cfg.backup_db_dir / cfg.sqlite_filename


def _set_partial_sqlite_manifest(backup_root: Path) -> None:
    sqlite_path = _sqlite_manifest_path(backup_root)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute("PRAGMA user_version=0")
        conn.commit()


def test_run_update_repairs_partial_sqlite_manifest_for_write_flow(
    tmp_path: Path,
) -> None:
    backup = tmp_path / "backup"
    source_v1 = tmp_path / "src-v1"
    source_v2 = tmp_path / "src-v2"

    source_v1.mkdir()
    (source_v1 / "file.txt").write_text("v1", encoding="utf-8")
    run_new(NewCommand(version="v1", source=str(source_v1), location=str(backup)))

    _set_partial_sqlite_manifest(backup)

    source_v2.mkdir()
    (source_v2 / "file.txt").write_text("v2", encoding="utf-8")
    run_update(UpdateCommand(version="v2", source=str(source_v2), location=str(backup)))

    errors = run_verify_integrity(
        VerifyIntegrityCommand(location=str(backup), version="v2")
    )
    assert errors == []


def test_run_restore_fails_fast_for_partial_sqlite_manifest_on_read_flow(
    tmp_path: Path,
) -> None:
    backup = tmp_path / "backup"
    restore_dest = tmp_path / "restore"
    backup.mkdir(parents=True, exist_ok=True)
    _set_partial_sqlite_manifest(backup)

    with pytest.raises(CliUsageError, match=r"SQLite manifest:.*not ready for read"):
        run_restore(
            RestoreCommand(
                location=str(backup),
                destination=str(restore_dest),
                version_name="v1",
            )
        )


def test_run_verify_integrity_fails_fast_for_partial_sqlite_manifest_on_read_flow(
    tmp_path: Path,
) -> None:
    backup = tmp_path / "backup"
    backup.mkdir(parents=True, exist_ok=True)
    _set_partial_sqlite_manifest(backup)

    with pytest.raises(CliUsageError, match=r"SQLite manifest:.*not ready for read"):
        run_verify_integrity(VerifyIntegrityCommand(location=str(backup)))


def test_force_csv_override_wins_when_mixed_manifests_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup = tmp_path / "backup"
    source_v1 = tmp_path / "src-v1"
    source_v2 = tmp_path / "src-v2"

    source_v1.mkdir()
    (source_v1 / "file.txt").write_text("v1", encoding="utf-8")
    run_new(NewCommand(version="v1", source=str(source_v1), location=str(backup)))

    csv_dir = backup / "db"
    csv_dir.mkdir(parents=True, exist_ok=True)
    (csv_dir / "legacy.csv").write_text('"d",".",""\n', encoding="utf-8")
    assert _sqlite_manifest_path(backup).exists()

    monkeypatch.setenv("FORCE_CSV_DB", "1")
    source_v2.mkdir()
    (source_v2 / "file.txt").write_text("v2", encoding="utf-8")
    run_update(UpdateCommand(version="v2", source=str(source_v2), location=str(backup)))

    assert (csv_dir / "v2.csv").exists()
