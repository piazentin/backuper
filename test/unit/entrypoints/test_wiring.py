from __future__ import annotations

import asyncio
from pathlib import Path

from backuper.entrypoints.wiring import create_backup_database
from backuper.ports import BackupDatabase


def test_create_backup_database_returns_backup_database(tmp_path: Path) -> None:
    db = create_backup_database(tmp_path)

    assert isinstance(db, BackupDatabase)

    asyncio.run(db.create_version("v1"))
    assert asyncio.run(db.list_versions()) == ["v1"]


def test_create_backup_database_accepts_index_status_callback(tmp_path: Path) -> None:
    calls: list[str] = []

    create_backup_database(tmp_path, index_status=calls.append)

    assert calls == ["Building index", "Index built"]
