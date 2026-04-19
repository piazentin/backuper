import sqlite3
from pathlib import Path
from uuid import UUID

import pytest
from backuper.components.sqlite_db import SqliteBackupDatabase, SqliteDb
from backuper.config import SqliteDbConfig
from backuper.models import BackedUpFileEntry, FileEntry, VersionNotFoundError


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    return {row[0] for row in rows}


def _index_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    return {row[0] for row in rows}


def test_bootstrap_creates_schema_v1_and_sets_user_version(tmp_path: Path) -> None:
    db = SqliteDb(SqliteDbConfig(backup_dir=str(tmp_path)))

    assert db.db_path.exists()
    assert db.db_path.parent == tmp_path / "db"

    with db.connect() as conn:
        user_version = conn.execute("PRAGMA user_version").fetchone()
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()

    assert user_version is not None
    assert foreign_keys is not None
    assert journal_mode is not None
    assert user_version[0] == 1
    assert foreign_keys[0] == 1
    assert journal_mode[0] == "wal"
    assert {"versions", "version_files", "version_directories"} <= _table_names(
        db.db_path
    )
    assert {
        "idx_versions_state_created_name",
        "idx_version_files_hash",
        "idx_version_files_metadata",
        "idx_version_files_version_name_id",
        "idx_version_directories_version_name_id",
    } <= _index_names(db.db_path)


def test_bootstrap_reopen_is_idempotent_and_preserves_data(tmp_path: Path) -> None:
    first = SqliteDb(SqliteDbConfig(backup_dir=str(tmp_path)))
    with first.connect() as conn:
        conn.execute(
            "INSERT INTO versions(name, state, created_at) VALUES (?, ?, ?)",
            ("v1", "pending", 1700000000.0),
        )
        conn.commit()

    second = SqliteDb(SqliteDbConfig(backup_dir=str(tmp_path)))
    with second.connect() as conn:
        user_version = conn.execute("PRAGMA user_version").fetchone()
        rows = conn.execute(
            "SELECT name, state, created_at FROM versions WHERE name = ?",
            ("v1",),
        ).fetchall()

    assert user_version is not None
    assert user_version[0] == 1
    assert [tuple(row) for row in rows] == [("v1", "pending", 1700000000.0)]


@pytest.mark.asyncio
async def test_sqlite_backup_database_pending_hidden_until_complete(
    tmp_path: Path,
) -> None:
    db = SqliteBackupDatabase(SqliteDb(SqliteDbConfig(backup_dir=str(tmp_path))))

    await db.create_version("v-pending")

    assert await db.list_versions() == []
    assert await db.most_recent_version() is None
    with pytest.raises(VersionNotFoundError):
        await db.get_version_by_name("v-pending")


@pytest.mark.asyncio
async def test_sqlite_backup_database_most_recent_uses_created_at_then_name(
    tmp_path: Path,
) -> None:
    sqlite_db = SqliteDb(SqliteDbConfig(backup_dir=str(tmp_path)))
    db = SqliteBackupDatabase(sqlite_db)

    with sqlite_db.connect() as conn:
        conn.execute(
            "INSERT INTO versions(name, state, created_at) VALUES (?, ?, ?)",
            ("a", "completed", 100.0),
        )
        conn.execute(
            "INSERT INTO versions(name, state, created_at) VALUES (?, ?, ?)",
            ("b", "completed", 100.0),
        )
        conn.execute(
            "INSERT INTO versions(name, state, created_at) VALUES (?, ?, ?)",
            ("older", "completed", 90.0),
        )
        conn.commit()

    assert await db.list_versions() == ["a", "b", "older"]
    assert await db.most_recent_version() == "b"


@pytest.mark.asyncio
async def test_sqlite_backup_database_add_and_list_files_files_then_dirs(
    tmp_path: Path,
) -> None:
    db = SqliteBackupDatabase(SqliteDb(SqliteDbConfig(backup_dir=str(tmp_path))))
    version = "v1"
    await db.create_version(version)
    await db.add_file(
        version,
        BackedUpFileEntry(
            source_file=FileEntry(
                path=Path("/src/z.txt"),
                relative_path=Path("z.txt"),
                size=2,
                mtime=2.0,
                is_directory=False,
            ),
            backup_id=UUID("11111111-1111-1111-1111-111111111111"),
            stored_location="data/z",
            is_compressed=False,
            hash="hz",
        ),
    )
    await db.add_file(
        version,
        BackedUpFileEntry(
            source_file=FileEntry(
                path=Path("/src/a-dir"),
                relative_path=Path("a-dir"),
                size=0,
                mtime=0.0,
                is_directory=True,
            ),
            backup_id=UUID("22222222-2222-2222-2222-222222222222"),
            stored_location="",
            is_compressed=False,
            hash="",
        ),
    )
    await db.add_file(
        version,
        BackedUpFileEntry(
            source_file=FileEntry(
                path=Path("/src/a.txt"),
                relative_path=Path("a.txt"),
                size=1,
                mtime=1.0,
                is_directory=False,
            ),
            backup_id=UUID("33333333-3333-3333-3333-333333333333"),
            stored_location="data/a",
            is_compressed=True,
            hash="ha",
        ),
    )
    await db.complete_version(version)

    items = [item async for item in db.list_files(version)]

    assert [item.relative_path for item in items] == [
        Path("z.txt"),
        Path("a.txt"),
        Path("a-dir"),
    ]
    assert [item.is_directory for item in items] == [False, False, True]
    assert items[0].is_compressed is False
    assert items[1].is_compressed is True


@pytest.mark.asyncio
async def test_sqlite_backup_database_lookup_only_completed_versions(
    tmp_path: Path,
) -> None:
    db = SqliteBackupDatabase(SqliteDb(SqliteDbConfig(backup_dir=str(tmp_path))))

    await db.create_version("v-pending")
    await db.add_file(
        "v-pending",
        BackedUpFileEntry(
            source_file=FileEntry(
                path=Path("/src/doc.txt"),
                relative_path=Path("doc.txt"),
                size=10,
                mtime=10.0,
                is_directory=False,
            ),
            backup_id=UUID("44444444-4444-4444-4444-444444444444"),
            stored_location="data/pending",
            is_compressed=False,
            hash="h1",
        ),
    )

    assert await db.get_files_by_hash("h1") == []
    assert await db.get_files_by_metadata(Path("doc.txt"), 10.0, 10) == []

    await db.complete_version("v-pending")

    by_hash = await db.get_files_by_hash("h1")
    by_metadata = await db.get_files_by_metadata(Path("doc.txt"), 10.0, 10)
    assert len(by_hash) == 1
    assert by_hash[0].stored_location == "data/pending"
    assert len(by_metadata) == 1
    assert by_metadata[0].source_file.relative_path == Path("doc.txt")


@pytest.mark.asyncio
async def test_sqlite_backup_database_cannot_add_file_to_completed_version(
    tmp_path: Path,
) -> None:
    db = SqliteBackupDatabase(SqliteDb(SqliteDbConfig(backup_dir=str(tmp_path))))
    version = "v-completed"
    await db.create_version(version)
    await db.complete_version(version)

    with pytest.raises(ValueError, match="completed"):
        await db.add_file(
            version,
            BackedUpFileEntry(
                source_file=FileEntry(
                    path=Path("/src/doc.txt"),
                    relative_path=Path("doc.txt"),
                    size=10,
                    mtime=10.0,
                    is_directory=False,
                ),
                backup_id=UUID("55555555-5555-5555-5555-555555555555"),
                stored_location="data/completed",
                is_compressed=False,
                hash="h2",
            ),
        )
