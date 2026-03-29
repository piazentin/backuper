from pathlib import Path

import pytest

from backuper.implementation.components.backup_analyzer import BackupAnalyzerImpl
from backuper.implementation.components.csv_db import CsvBackupDatabase, CsvDb
from backuper.implementation.components.file_reader import LocalFileReader
from backuper.implementation.components.filestore import LocalFileStore
from backuper.implementation.config import CsvDbConfig, FilestoreConfig
from backuper.implementation.controllers.create_backup import CreateBackupController


@pytest.mark.asyncio
async def test_create_backup_writes_data_store_and_metadata(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "subdir").mkdir()

    duplicated_content = b"same content for hash dedup"
    (source / "a.txt").write_bytes(duplicated_content)
    (source / "subdir" / "b.txt").write_bytes(duplicated_content)

    backup_root = tmp_path / "backup"
    version = "20260329093000"

    db = CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=str(backup_root))))
    controller = CreateBackupController(
        file_reader=LocalFileReader(),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=LocalFileStore(
            FilestoreConfig(
                backup_dir=str(backup_root),
                zip_enabled=False,
            )
        ),
    )

    await controller.create_backup(source=source, version=version)

    backed_up_entries = []
    async for item in db.list_files(version):
        backed_up_entries.append(item)

    file_entries = [entry for entry in backed_up_entries if not entry.is_directory]
    dir_entries = [entry for entry in backed_up_entries if entry.is_directory]

    assert len(file_entries) == 2
    assert len(dir_entries) == 1
    assert dir_entries[0].relative_path == Path("subdir")

    by_hash = await db.get_files_by_hash(file_entries[0].hash)
    assert len(by_hash) == 2
    assert len({entry.stored_location for entry in by_hash}) == 1

    stored_location = by_hash[0].stored_location
    stored_file = backup_root / "data" / stored_location
    assert stored_file.exists()
