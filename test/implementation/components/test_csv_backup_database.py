from pathlib import Path
from uuid import UUID

import pytest

from backuper.implementation.components.csv_db import CsvBackupDatabase, CsvDb
from backuper.implementation.components.interfaces import BackupedFileEntry, FileEntry
from backuper.implementation.config import CsvDbConfig


@pytest.mark.asyncio
async def test_csv_backup_database_create_version_and_list_versions(tmp_path: Path) -> None:
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    db = CsvBackupDatabase(csv_db)

    await db.create_version("2026.03.29")
    await db.create_version("v.scsv")

    assert sorted(await db.list_versions()) == ["2026.03.29", "v.scsv"]


@pytest.mark.asyncio
async def test_csv_backup_database_add_and_lookup_file_entries(tmp_path: Path) -> None:
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    db = CsvBackupDatabase(csv_db)
    await db.create_version("20260329000000")

    file_entry = FileEntry(
        path=Path("/src/docs/readme.txt"),
        relative_path=Path("docs/readme.txt"),
        size=42,
        mtime=1711700000.123,
        is_directory=False,
    )
    stored_file = BackupedFileEntry(
        source_file=file_entry,
        backup_id=UUID("11111111-1111-1111-1111-111111111111"),
        stored_location="data/f1",
        is_compressed=False,
        hash="abc123",
    )
    second_file_entry = FileEntry(
        path=Path("/src/docs/notes.txt"),
        relative_path=Path("docs/notes.txt"),
        size=12,
        mtime=1711700001.0,
        is_directory=False,
    )
    second_stored_file = BackupedFileEntry(
        source_file=second_file_entry,
        backup_id=UUID("33333333-3333-3333-3333-333333333333"),
        stored_location="data/f2",
        is_compressed=False,
        hash="def456",
    )

    await db.add_file("20260329000000", stored_file)
    await db.add_file("20260329000000", second_stored_file)

    by_metadata = await db.get_files_by_metadata(Path("docs/readme.txt"), 1711700000.123, 42)
    assert len(by_metadata) == 1
    assert by_metadata[0].stored_location == "data/f1"
    assert by_metadata[0].hash == "abc123"
    assert by_metadata[0].source_file.relative_path == Path("docs/readme.txt")

    by_hash = await db.get_files_by_hash("abc123")
    assert len(by_hash) == 1
    assert by_hash[0].source_file.relative_path == Path("docs/readme.txt")

    second_by_metadata = await db.get_files_by_metadata(Path("docs/notes.txt"), 1711700001.0, 12)
    assert len(second_by_metadata) == 1
    assert second_by_metadata[0].stored_location == "data/f2"
    assert second_by_metadata[0].hash == "def456"
    assert second_by_metadata[0].source_file.relative_path == Path("docs/notes.txt")

    second_by_hash = await db.get_files_by_hash("def456")
    assert len(second_by_hash) == 1
    assert second_by_hash[0].source_file.relative_path == Path("docs/notes.txt")


@pytest.mark.asyncio
async def test_csv_backup_database_add_and_list_directory_entries(tmp_path: Path) -> None:
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    db = CsvBackupDatabase(csv_db)
    await db.create_version("20260329010000")

    dir_entry = BackupedFileEntry(
        source_file=FileEntry(
            path=Path("/src/subdir"),
            relative_path=Path("subdir"),
            size=0,
            mtime=0.0,
            is_directory=True,
        ),
        backup_id=UUID("22222222-2222-2222-2222-222222222222"),
        stored_location="",
        is_compressed=False,
        hash="",
    )
    await db.add_file("20260329010000", dir_entry)

    items = []
    async for item in db.list_files("20260329010000"):
        items.append(item)

    assert len(items) == 1
    assert items[0].is_directory is True
    assert items[0].relative_path == Path("subdir")
