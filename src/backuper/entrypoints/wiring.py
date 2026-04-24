from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal

from backuper.components.sqlite_db import (
    SqliteBackupDatabase,
    SqliteDb,
    configure_sqlite_read_probe_connection,
)
from backuper.config import SqliteDbConfig, sqlite_db_config
from backuper.models import CliUsageError
from backuper.ports import BackupDatabase

_SQLITE_REQUIRED_TABLES = {"versions", "version_files", "version_directories"}
_SQLITE_CLI_PREFIX = "SQLite manifest: "
_LEGACY_LAYOUT_GUARD = (
    _SQLITE_CLI_PREFIX
    + "The manifest database is missing or not usable for this backup."
)
_RESOLUTION_GUIDANCE = (
    _SQLITE_CLI_PREFIX + "The manifest is not ready for read operations. "
    "Run a write command (new/update) to initialize or repair the SQLite backend."
)
_MISSING_SQLITE_MANIFEST_GUIDANCE = (
    _SQLITE_CLI_PREFIX + "No database file found for read operations. "
    "Run a write command (new/update) to create the SQLite backend."
)
_SQLITE_BOOTSTRAP_GUIDANCE = (
    _SQLITE_CLI_PREFIX + "The backend could not be initialized. "
    "Run a write command (new/update) to initialize or repair the SQLite backend."
)


def _sqlite_manifest_path(backup_root: Path) -> Path:
    config = SqliteDbConfig(backup_dir=str(backup_root))
    return backup_root / config.backup_db_dir / config.sqlite_filename


def _has_canonical_csv_manifest(backup_root: Path) -> bool:
    config = SqliteDbConfig(backup_dir=str(backup_root))
    db_dir = backup_root / config.backup_db_dir
    if not db_dir.exists() or not db_dir.is_dir():
        return False
    return any(
        candidate.is_file()
        and candidate.suffix == ".csv"
        and not candidate.name.startswith(".")
        for candidate in db_dir.iterdir()
    )


def _validate_sqlite_manifest_for_read(sqlite_manifest_path: Path) -> None:
    if not sqlite_manifest_path.exists():
        raise CliUsageError(_MISSING_SQLITE_MANIFEST_GUIDANCE)
    try:
        with closing(
            sqlite3.connect(f"file:{sqlite_manifest_path}?mode=ro", uri=True)
        ) as conn:
            configure_sqlite_read_probe_connection(conn)
            version_row = conn.execute("PRAGMA user_version").fetchone()
            if version_row is None or int(version_row[0]) < 1:
                raise CliUsageError(_RESOLUTION_GUIDANCE)
            table_rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {str(row[0]) for row in table_rows}
            if not _SQLITE_REQUIRED_TABLES.issubset(table_names):
                raise CliUsageError(_RESOLUTION_GUIDANCE)
    except sqlite3.Error as exc:
        raise CliUsageError(_RESOLUTION_GUIDANCE) from exc


def create_backup_database(
    backup_root: Path,
    *,
    operation: Literal["read", "write"] = "write",
) -> BackupDatabase:
    """Build a backup database adapter based on backend resolution policy."""
    sqlite_manifest_path = _sqlite_manifest_path(backup_root)
    if _has_canonical_csv_manifest(backup_root) and not sqlite_manifest_path.exists():
        raise CliUsageError(_LEGACY_LAYOUT_GUARD)
    if operation == "read":
        _validate_sqlite_manifest_for_read(sqlite_manifest_path)
    try:
        config = sqlite_db_config(str(backup_root))
    except (RuntimeError, ValueError) as exc:
        # Invalid BACKUPER_SQLITE_SYNCHRONOUS (and other config parsing failures).
        raise CliUsageError(str(exc)) from exc
    try:
        return SqliteBackupDatabase(SqliteDb(config))
    except sqlite3.Error as exc:
        raise CliUsageError(_SQLITE_BOOTSTRAP_GUIDANCE) from exc
