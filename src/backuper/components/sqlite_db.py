from __future__ import annotations

import sqlite3
from pathlib import Path

from backuper.config import SqliteDbConfig


class SqliteDb:
    """SQLite bootstrapper for backup manifest storage."""

    _SCHEMA_VERSION = 1

    def __init__(self, config: SqliteDbConfig) -> None:
        self._config = config
        self.db_dir = Path(self._config.backup_dir) / self._config.backup_db_dir
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self.db_dir / self._config.sqlite_filename
        self._bootstrap()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        self._configure_connection(conn)
        return conn

    def _bootstrap(self) -> None:
        with self.connect() as conn:
            version_row = conn.execute("PRAGMA user_version").fetchone()
            if version_row is None:
                raise RuntimeError("Could not read PRAGMA user_version")
            current_version = int(version_row[0])
            if current_version > self._SCHEMA_VERSION:
                raise RuntimeError(
                    f"Unsupported SQLite schema version {current_version} "
                    f"(max supported: {self._SCHEMA_VERSION})"
                )
            if current_version < 1:
                self._migrate_to_v1(conn)
                conn.execute(f"PRAGMA user_version={self._SCHEMA_VERSION}")
            conn.commit()

    def _configure_connection(self, conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")

    def _migrate_to_v1(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS versions (
                name TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS version_files (
                id INTEGER PRIMARY KEY,
                version_name TEXT NOT NULL REFERENCES versions(name) ON DELETE CASCADE,
                restore_path TEXT NOT NULL,
                hash_algorithm TEXT NOT NULL,
                hash_digest TEXT NOT NULL,
                storage_location TEXT NOT NULL,
                compression TEXT NOT NULL,
                size INTEGER NOT NULL,
                mtime REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS version_directories (
                id INTEGER PRIMARY KEY,
                version_name TEXT NOT NULL REFERENCES versions(name) ON DELETE CASCADE,
                restore_path TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_versions_state_created_name
            ON versions(state, created_at DESC, name DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_version_files_hash
            ON version_files(hash_algorithm, hash_digest)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_version_files_metadata
            ON version_files(restore_path, mtime, size)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_version_files_version_name_id
            ON version_files(version_name, id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_version_directories_version_name_id
            ON version_directories(version_name, id)
            """
        )
