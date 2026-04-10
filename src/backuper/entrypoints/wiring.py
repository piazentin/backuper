from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from backuper.components.csv_db import CsvBackupDatabase, CsvDb
from backuper.config import CsvDbConfig
from backuper.ports import BackupDatabase


def create_backup_database(
    backup_root: Path,
    *,
    index_status: Callable[[str], None] | None = None,
) -> BackupDatabase:
    """Build the default backup database adapter for a backup root path."""
    return CsvBackupDatabase(
        CsvDb(CsvDbConfig(backup_dir=str(backup_root))),
        index_status=index_status,
    )
