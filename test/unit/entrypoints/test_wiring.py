from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from backuper.components.csv_db import CsvBackupDatabase
from backuper.components.sqlite_db import SqliteBackupDatabase
from backuper.config import BACKUPER_SQLITE_SYNCHRONOUS_ENV, SqliteDbConfig
from backuper.entrypoints.wiring import create_backup_database
from backuper.models import CliUsageError
from backuper.ports import BackupDatabase


@pytest.mark.asyncio
async def test_create_backup_database_returns_backup_database(tmp_path: Path) -> None:
    db = create_backup_database(tmp_path)

    assert isinstance(db, BackupDatabase)

    await db.create_version("v1")
    await db.complete_version("v1")
    assert await db.list_versions() == ["v1"]


def test_create_backup_database_accepts_index_status_callback(tmp_path: Path) -> None:
    calls: list[str] = []
    db_dir = tmp_path / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    (db_dir / "v1.csv").write_text('"d",".",""\n', encoding="utf-8")

    create_backup_database(tmp_path, index_status=calls.append)

    assert len(calls) >= 2
    assert all(isinstance(call, str) for call in calls)


def test_create_backup_database_defaults_to_sqlite_for_new_tree(tmp_path: Path) -> None:
    db = create_backup_database(tmp_path, operation="write")

    assert isinstance(db, SqliteBackupDatabase)


def test_create_backup_database_invalid_sqlite_synchronous_env_is_cli_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(BACKUPER_SQLITE_SYNCHRONOUS_ENV, "not-a-mode")

    with pytest.raises(CliUsageError, match="BACKUPER_SQLITE_SYNCHRONOUS"):
        create_backup_database(tmp_path, operation="write")


def test_create_backup_database_uses_csv_when_force_csv_override_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_dir = tmp_path / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = (
        tmp_path
        / SqliteDbConfig(backup_dir=str(tmp_path)).backup_db_dir
        / SqliteDbConfig(backup_dir=str(tmp_path)).sqlite_filename
    )
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite_path.write_text("placeholder", encoding="utf-8")
    (db_dir / "v1.csv").write_text('"d",".",""\n', encoding="utf-8")
    monkeypatch.setenv("FORCE_CSV_DB", "1")

    db = create_backup_database(tmp_path, operation="write")

    assert isinstance(db, CsvBackupDatabase)


def test_create_backup_database_prefers_sqlite_when_both_backends_exist(
    tmp_path: Path,
) -> None:
    db_dir = tmp_path / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    create_backup_database(tmp_path, operation="write")
    (db_dir / "v1.csv").write_text('"d",".",""\n', encoding="utf-8")

    db = create_backup_database(tmp_path, operation="write")

    assert isinstance(db, SqliteBackupDatabase)


def test_create_backup_database_detects_only_canonical_csv_files(
    tmp_path: Path,
) -> None:
    db_dir = tmp_path / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    (db_dir / ".pending__v2.csv").write_text('"d",".",""\n', encoding="utf-8")

    db = create_backup_database(tmp_path, operation="write")

    assert isinstance(db, SqliteBackupDatabase)


def test_create_backup_database_uses_csv_when_only_canonical_csv_exists(
    tmp_path: Path,
) -> None:
    db_dir = tmp_path / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    (db_dir / "v1.csv").write_text('"d",".",""\n', encoding="utf-8")

    db = create_backup_database(tmp_path, operation="write")

    assert isinstance(db, CsvBackupDatabase)


def test_create_backup_database_read_fails_for_partial_sqlite_manifest(
    tmp_path: Path,
) -> None:
    sqlite_path = (
        tmp_path
        / SqliteDbConfig(backup_dir=str(tmp_path)).backup_db_dir
        / SqliteDbConfig(backup_dir=str(tmp_path)).sqlite_filename
    )
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute("PRAGMA user_version=0")
        conn.commit()

    with pytest.raises(CliUsageError, match=r"SQLite manifest:.*not ready for read"):
        create_backup_database(tmp_path, operation="read")


def test_create_backup_database_read_fails_when_sqlite_manifest_is_missing(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        CliUsageError, match=r"SQLite manifest:.*No database file found"
    ):
        create_backup_database(tmp_path, operation="read")


def test_create_backup_database_read_maps_invalid_sqlite_file_to_usage_error(
    tmp_path: Path,
) -> None:
    sqlite_path = (
        tmp_path
        / SqliteDbConfig(backup_dir=str(tmp_path)).backup_db_dir
        / SqliteDbConfig(backup_dir=str(tmp_path)).sqlite_filename
    )
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite_path.write_text("not-a-sqlite-db", encoding="utf-8")

    with pytest.raises(CliUsageError, match=r"SQLite manifest:.*not ready for read"):
        create_backup_database(tmp_path, operation="read")


def test_create_backup_database_write_maps_invalid_sqlite_file_to_usage_error(
    tmp_path: Path,
) -> None:
    sqlite_path = (
        tmp_path
        / SqliteDbConfig(backup_dir=str(tmp_path)).backup_db_dir
        / SqliteDbConfig(backup_dir=str(tmp_path)).sqlite_filename
    )
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite_path.write_text("not-a-sqlite-db", encoding="utf-8")

    with pytest.raises(
        CliUsageError, match=r"SQLite manifest:.*could not be initialized"
    ):
        create_backup_database(tmp_path, operation="write")
