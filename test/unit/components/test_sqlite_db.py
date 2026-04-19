import sqlite3
from pathlib import Path

from backuper.components.sqlite_db import SqliteDb
from backuper.config import SqliteDbConfig


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
