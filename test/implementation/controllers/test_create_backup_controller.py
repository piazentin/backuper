from pathlib import Path
from typing import AsyncIterator
from uuid import UUID

import pytest

from backuper.implementation.components.backup_analyzer import BackupAnalyzerImpl
from backuper.implementation.components.csv_db import CsvBackupDatabase, CsvDb
from backuper.implementation.components.file_reader import LocalFileReader
from backuper.implementation.components.filestore import LocalFileStore
from backuper.implementation.components.interfaces import (
    AnalyzedFileEntry,
    AnalysisReporter,
    BackupDatabase,
    BackupAnalyzer,
    FileEntry,
    FileReader,
)
from backuper.implementation.config import CsvDbConfig, FilestoreConfig
from backuper.implementation.controllers.backup import (
    _analyze_path,
    add_version,
    new_backup,
)


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
    filestore = LocalFileStore(
        FilestoreConfig(
            backup_dir=str(backup_root),
            zip_enabled=False,
        )
    )

    await new_backup(
        source,
        version,
        file_reader=LocalFileReader(),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=filestore,
    )

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


@pytest.mark.asyncio
async def test_add_version_raises_when_version_already_exists(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.txt").write_bytes(b"x")

    backup_root = tmp_path / "backup"
    version = "v1"

    db = CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=str(backup_root))))
    filestore = LocalFileStore(
        FilestoreConfig(
            backup_dir=str(backup_root),
            zip_enabled=False,
        )
    )

    await new_backup(
        source,
        version,
        file_reader=LocalFileReader(),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=filestore,
    )
    with pytest.raises(ValueError, match="already a backup versioned"):
        await add_version(
            source,
            version,
            file_reader=LocalFileReader(),
            analyzer=BackupAnalyzerImpl(),
            db=db,
            filestore=filestore,
        )


class _ReaderStub(FileReader):
    async def read_directory(self, path: Path) -> AsyncIterator[FileEntry]:
        yield FileEntry(
            path=path / "file.txt",
            relative_path=Path("file.txt"),
            size=10,
            mtime=100.0,
            is_directory=False,
        )


class _AnalyzerStub(BackupAnalyzer):
    async def analyze_stream(
        self, entries: AsyncIterator[FileEntry], backup_database: BackupDatabase
    ) -> AsyncIterator[AnalyzedFileEntry]:
        async for entry in entries:
            yield AnalyzedFileEntry(
                source_file=entry,
                hash="hash123",
                already_backed_up=True,
                backup_id=UUID("12345678-1234-5678-1234-567812345678"),
            )


class _DbStub(BackupDatabase):
    async def list_versions(self):
        return []

    async def list_files(self, version: str):
        if False:
            yield

    async def create_version(self, version: str) -> None:
        pass

    async def add_file(self, version: str, entry):
        pass

    async def get_files_by_hash(self, hash: str):
        return []

    async def get_files_by_metadata(self, relative_path: Path, mtime: float, size: int):
        return []


class _CollectingReporter(AnalysisReporter):
    def __init__(self) -> None:
        self.entries = []

    def report(self, entry: AnalyzedFileEntry) -> None:
        self.entries.append(entry)


@pytest.mark.asyncio
async def test_analyze_path_reports_structured_entries(tmp_path: Path) -> None:
    reporter = _CollectingReporter()
    await _analyze_path(
        tmp_path,
        file_reader=_ReaderStub(),
        analyzer=_AnalyzerStub(),
        db=_DbStub(),
        reporter=reporter,
    )

    assert len(reporter.entries) == 1
    reported = reporter.entries[0]
    assert reported.source_file.relative_path == Path("file.txt")
    assert reported.already_backed_up is True
    assert reported.backup_id == UUID("12345678-1234-5678-1234-567812345678")
