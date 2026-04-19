from __future__ import annotations

import sqlite3
import time
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import UUID

from backuper.config import SqliteDbConfig
from backuper.models import (
    BackedUpFileEntry,
    FileEntry,
    VersionAlreadyExistsError,
    VersionNotFoundError,
)
from backuper.ports import BackupDatabase

SQL_SELECT_COMPLETED_VERSION_NAMES = (
    "SELECT name FROM versions WHERE state = ? ORDER BY name ASC"
)
SQL_SELECT_MOST_RECENT_COMPLETED_VERSION = """
SELECT name
FROM versions
WHERE state = ?
ORDER BY created_at DESC, name DESC
LIMIT 1
"""
SQL_SELECT_COMPLETED_VERSION_BY_NAME = (
    "SELECT name FROM versions WHERE name = ? AND state = ?"
)
SQL_SELECT_FILES_BY_VERSION = """
SELECT restore_path, hash_digest, storage_location, compression, size, mtime
FROM version_files
WHERE version_name = ?
ORDER BY id ASC
"""
SQL_SELECT_DIRECTORIES_BY_VERSION = """
SELECT restore_path
FROM version_directories
WHERE version_name = ?
ORDER BY id ASC
"""
SQL_INSERT_VERSION = "INSERT INTO versions(name, state, created_at) VALUES (?, ?, ?)"
SQL_INSERT_DIRECTORY = """
INSERT INTO version_directories(version_name, restore_path)
VALUES (?, ?)
"""
SQL_INSERT_FILE = """
INSERT INTO version_files(
    version_name,
    restore_path,
    hash_algorithm,
    hash_digest,
    storage_location,
    compression,
    size,
    mtime
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""
SQL_SELECT_FILES_BY_HASH = """
SELECT vf.restore_path, vf.hash_digest, vf.storage_location, vf.compression,
       vf.size, vf.mtime
FROM version_files vf
INNER JOIN versions v ON v.name = vf.version_name
WHERE v.state = ? AND vf.hash_algorithm = ? AND vf.hash_digest = ?
ORDER BY vf.id ASC
"""
SQL_SELECT_FILES_BY_METADATA = """
SELECT vf.restore_path, vf.hash_digest, vf.storage_location, vf.compression,
       vf.size, vf.mtime
FROM version_files vf
INNER JOIN versions v ON v.name = vf.version_name
WHERE v.state = ?
  AND vf.restore_path = ?
  AND vf.mtime > ?
  AND vf.mtime < ?
  AND vf.size = ?
ORDER BY vf.id ASC
"""


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


class SqliteBackupDatabase(BackupDatabase):
    _DEFAULT_HASH_ALGORITHM = "sha1"
    _COMPRESSION_NONE = "none"
    _COMPRESSION_ZIP = "zip"
    _VERSION_STATE_PENDING = "pending"
    _VERSION_STATE_COMPLETED = "completed"
    _MTIME_TOLERANCE_SECONDS = 0.001

    def __init__(self, sqlite_db: SqliteDb) -> None:
        self._sqlite_db = sqlite_db

    async def list_versions(self) -> list[str]:
        with self._sqlite_db.connect() as conn:
            rows = conn.execute(
                SQL_SELECT_COMPLETED_VERSION_NAMES,
                (self._VERSION_STATE_COMPLETED,),
            ).fetchall()
        return [str(row["name"]) for row in rows]

    async def most_recent_version(self) -> str | None:
        with self._sqlite_db.connect() as conn:
            row = conn.execute(
                SQL_SELECT_MOST_RECENT_COMPLETED_VERSION,
                (self._VERSION_STATE_COMPLETED,),
            ).fetchone()
        if row is None:
            return None
        return str(row["name"])

    async def get_version_by_name(self, name: str) -> str:
        with self._sqlite_db.connect() as conn:
            row = conn.execute(
                SQL_SELECT_COMPLETED_VERSION_BY_NAME,
                (name, self._VERSION_STATE_COMPLETED),
            ).fetchone()
        if row is None:
            raise VersionNotFoundError(name)
        return str(row["name"])

    async def list_files(self, version: str) -> AsyncGenerator[FileEntry, None]:
        with self._sqlite_db.connect() as conn:
            version_row = conn.execute(
                "SELECT name FROM versions WHERE name = ? AND state = ?",
                (version, self._VERSION_STATE_COMPLETED),
            ).fetchone()
            if version_row is None:
                raise VersionNotFoundError(version)

            file_rows = conn.execute(
                SQL_SELECT_FILES_BY_VERSION,
                (version,),
            ).fetchall()
            dir_rows = conn.execute(
                SQL_SELECT_DIRECTORIES_BY_VERSION,
                (version,),
            ).fetchall()

        for row in file_rows:
            restore_path = Path(str(row["restore_path"]))
            yield FileEntry(
                path=restore_path,
                relative_path=restore_path,
                size=int(row["size"]),
                mtime=float(row["mtime"]),
                is_directory=False,
                hash=str(row["hash_digest"]),
                stored_location=str(row["storage_location"]),
                is_compressed=str(row["compression"]) == self._COMPRESSION_ZIP,
            )

        for row in dir_rows:
            restore_path = Path(str(row["restore_path"]))
            yield FileEntry(
                path=restore_path,
                relative_path=restore_path,
                size=0,
                mtime=0.0,
                is_directory=True,
            )

    async def create_version(self, version: str) -> None:
        with self._sqlite_db.connect() as conn:
            try:
                conn.execute(
                    SQL_INSERT_VERSION,
                    (version, self._VERSION_STATE_PENDING, time.time()),
                )
            except sqlite3.IntegrityError as exc:
                raise VersionAlreadyExistsError(version) from exc
            conn.commit()

    async def complete_version(self, version: str) -> None:
        with self._sqlite_db.connect() as conn:
            completed_row = conn.execute(
                "SELECT 1 FROM versions WHERE name = ? AND state = ?",
                (version, self._VERSION_STATE_COMPLETED),
            ).fetchone()
            if completed_row is not None:
                return

            pending_row = conn.execute(
                "SELECT 1 FROM versions WHERE name = ? AND state = ?",
                (version, self._VERSION_STATE_PENDING),
            ).fetchone()
            if pending_row is None:
                raise VersionNotFoundError(version)

            conn.execute(
                "UPDATE versions SET state = ? WHERE name = ?",
                (self._VERSION_STATE_COMPLETED, version),
            )
            conn.commit()

    async def add_file(self, version: str, entry: BackedUpFileEntry) -> None:
        with self._sqlite_db.connect() as conn:
            self._require_pending_version(conn, version)

            if entry.source_file.is_directory:
                conn.execute(
                    SQL_INSERT_DIRECTORY,
                    (version, str(entry.source_file.relative_path)),
                )
                conn.commit()
                return

            conn.execute(
                SQL_INSERT_FILE,
                (
                    version,
                    str(entry.source_file.relative_path),
                    self._DEFAULT_HASH_ALGORITHM,
                    entry.hash,
                    entry.stored_location,
                    self._COMPRESSION_ZIP
                    if entry.is_compressed
                    else self._COMPRESSION_NONE,
                    entry.source_file.size,
                    entry.source_file.mtime,
                ),
            )
            conn.commit()

    def _require_pending_version(self, conn: sqlite3.Connection, version: str) -> None:
        pending_row = conn.execute(
            "SELECT 1 FROM versions WHERE name = ? AND state = ?",
            (version, self._VERSION_STATE_PENDING),
        ).fetchone()
        if pending_row is not None:
            return

        completed_row = conn.execute(
            "SELECT 1 FROM versions WHERE name = ? AND state = ?",
            (version, self._VERSION_STATE_COMPLETED),
        ).fetchone()
        if completed_row is not None:
            raise ValueError(f"Cannot add files to completed version {version!r}.")

        raise VersionNotFoundError(version)

    async def get_files_by_hash(self, hash: str) -> list[BackedUpFileEntry]:
        with self._sqlite_db.connect() as conn:
            rows = conn.execute(
                SQL_SELECT_FILES_BY_HASH,
                (
                    self._VERSION_STATE_COMPLETED,
                    self._DEFAULT_HASH_ALGORITHM,
                    hash,
                ),
            ).fetchall()
        return [self._row_to_backed_up_file_entry(row) for row in rows]

    async def get_files_by_metadata(
        self, relative_path: Path, mtime: float, size: int
    ) -> list[BackedUpFileEntry]:
        lower_bound = mtime - self._MTIME_TOLERANCE_SECONDS
        upper_bound = mtime + self._MTIME_TOLERANCE_SECONDS
        with self._sqlite_db.connect() as conn:
            rows = conn.execute(
                SQL_SELECT_FILES_BY_METADATA,
                (
                    self._VERSION_STATE_COMPLETED,
                    str(relative_path),
                    lower_bound,
                    upper_bound,
                    size,
                ),
            ).fetchall()
        return [self._row_to_backed_up_file_entry(row) for row in rows]

    def _row_to_backed_up_file_entry(self, row: sqlite3.Row) -> BackedUpFileEntry:
        restore_path = Path(str(row["restore_path"]))
        file_entry = FileEntry(
            path=restore_path,
            relative_path=restore_path,
            size=int(row["size"]),
            mtime=float(row["mtime"]),
            is_directory=False,
        )
        return BackedUpFileEntry(
            source_file=file_entry,
            backup_id=self._generate_uuid_from_hash(str(row["hash_digest"])),
            stored_location=str(row["storage_location"]),
            is_compressed=str(row["compression"]) == self._COMPRESSION_ZIP,
            hash=str(row["hash_digest"]),
        )

    def _generate_uuid_from_hash(self, hash_value: str) -> UUID:
        return uuid.uuid5(uuid.NAMESPACE_DNS, hash_value)
