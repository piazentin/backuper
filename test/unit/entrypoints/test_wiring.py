from __future__ import annotations

from pathlib import Path

import pytest
from backuper.entrypoints.wiring import create_backup_database
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

    create_backup_database(tmp_path, index_status=calls.append)

    assert len(calls) >= 2
    assert all(isinstance(call, str) for call in calls)
