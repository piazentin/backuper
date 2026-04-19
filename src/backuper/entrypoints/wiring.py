from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Literal

from backuper.components.csv_db import CsvBackupDatabase, CsvDb
from backuper.components.sqlite_db import SqliteBackupDatabase, SqliteDb
from backuper.config import CsvDbConfig, SqliteDbConfig
from backuper.models import CliUsageError
from backuper.ports import BackupDatabase

_FORCE_CSV_DB_ENV = "FORCE_CSV_DB"
_SQLITE_REQUIRED_TABLES = {"versions", "version_files", "version_directories"}
_RESOLUTION_GUIDANCE = (
    "The SQLite manifest is not ready for read operations. "
    "Run a write command (new/update) to initialize or repair the SQLite backend, "
    "or set FORCE_CSV_DB=1 to force CSV backend selection."
)
_MISSING_SQLITE_MANIFEST_GUIDANCE = (
    "No SQLite manifest found for read operation. "
    "Run a write command (new/update) to create the SQLite backend, "
    "or set FORCE_CSV_DB=1 to force CSV backend selection."
)
_SQLITE_BOOTSTRAP_GUIDANCE = (
    "The SQLite backend could not be initialized. "
    "Run a write command (new/update) to initialize or repair the SQLite backend, "
    "or set FORCE_CSV_DB=1 to force CSV backend selection."
)


def _sqlite_manifest_path(backup_root: Path) -> Path:
    config = SqliteDbConfig(backup_dir=str(backup_root))
    return (
        backup_root
        / config.backup_db_dir
        / config.sqlite_filename
    )


def _has_canonical_csv_manifest(backup_root: Path) -> bool:
    config = CsvDbConfig(backup_dir=str(backup_root))
    db_dir = backup_root / config.backup_db_dir
    if not db_dir.exists() or not db_dir.is_dir():
        return False
    return any(
        candidate.is_file()
        and candidate.suffix == config.csv_file_extension
        and not candidate.name.startswith(".")
        for candidate in db_dir.iterdir()
    )


def _is_force_csv_enabled() -> bool:
    return os.getenv(_FORCE_CSV_DB_ENV) == "1"


def _resolve_backend(backup_root: Path) -> Literal["csv", "sqlite"]:
    if _is_force_csv_enabled():
        return "csv"
    if _sqlite_manifest_path(backup_root).exists():
        return "sqlite"
    if _has_canonical_csv_manifest(backup_root):
        return "csv"
    return "sqlite"


def _validate_sqlite_manifest_for_read(sqlite_manifest_path: Path) -> None:
    if not sqlite_manifest_path.exists():
        raise CliUsageError(_MISSING_SQLITE_MANIFEST_GUIDANCE)
    try:
        with closing(
            sqlite3.connect(f"file:{sqlite_manifest_path}?mode=ro", uri=True)
        ) as conn:
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
    index_status: Callable[[str], None] | None = None,
) -> BackupDatabase:
    """Build a backup database adapter based on backend resolution policy."""
    backend = _resolve_backend(backup_root)
    if backend == "csv":
        return CsvBackupDatabase(
            CsvDb(CsvDbConfig(backup_dir=str(backup_root))),
            index_status=index_status,
        )

    sqlite_manifest_path = _sqlite_manifest_path(backup_root)
    if operation == "read":
        _validate_sqlite_manifest_for_read(sqlite_manifest_path)
    try:
        return SqliteBackupDatabase(SqliteDb(SqliteDbConfig(backup_dir=str(backup_root))))
    except sqlite3.Error as exc:
        raise CliUsageError(_SQLITE_BOOTSTRAP_GUIDANCE) from exc
