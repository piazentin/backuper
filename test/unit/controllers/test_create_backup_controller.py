from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

import pytest
from backuper.components.backup_analyzer import BackupAnalyzerImpl
from backuper.components.csv_db import CsvBackupDatabase, CsvDb
from backuper.components.file_reader import LocalFileReader
from backuper.components.filestore import LocalFileStore
from backuper.components.path_ignore import NullPathFilter
from backuper.components.reporter import NoOpAnalysisReporter
from backuper.config import CsvDbConfig, FilestoreConfig
from backuper.controllers.backup import (
    _iterate_analyzed_entries,
    add_version,
    new_backup,
)
from backuper.models import (
    AnalyzedFileEntry,
    BackupAnalysisSummary,
    FileEntry,
    VersionAlreadyExistsError,
)
from backuper.ports import (
    AnalysisReporter,
    BackupAnalyzer,
    BackupDatabase,
    FileReader,
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
        file_reader=LocalFileReader(path_filter=NullPathFilter()),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=filestore,
        reporter=NoOpAnalysisReporter(),
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
        file_reader=LocalFileReader(path_filter=NullPathFilter()),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=filestore,
        reporter=NoOpAnalysisReporter(),
    )
    with pytest.raises(
        VersionAlreadyExistsError,
        match="already a backup versioned",
    ):
        await add_version(
            source,
            version,
            file_reader=LocalFileReader(path_filter=NullPathFilter()),
            analyzer=BackupAnalyzerImpl(),
            db=db,
            filestore=filestore,
            reporter=NoOpAnalysisReporter(),
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
    def __init__(self, *, fail_on_add_file: bool = False) -> None:
        self.fail_on_add_file = fail_on_add_file
        self.completed_versions: list[str] = []

    async def list_versions(self):
        return []

    async def most_recent_version(self) -> str | None:
        return None

    async def get_version_by_name(self, name: str) -> str:
        return name

    async def list_files(self, version: str):
        if False:
            yield

    async def create_version(self, version: str) -> None:
        pass

    async def add_file(self, version: str, entry):
        if self.fail_on_add_file:
            raise RuntimeError("simulated write failure")
        pass

    async def complete_version(self, version: str) -> None:
        self.completed_versions.append(version)

    async def get_files_by_hash(self, hash: str):
        return []

    async def get_files_by_metadata(self, relative_path: Path, mtime: float, size: int):
        return []


class _CollectingReporter(AnalysisReporter):
    def __init__(self) -> None:
        self.entries: list[AnalyzedFileEntry] = []

    def report(self, entry: AnalyzedFileEntry) -> None:
        self.entries.append(entry)

    def report_analysis_start(self) -> None:
        pass

    def report_analysis_summary(self, summary: BackupAnalysisSummary) -> None:
        pass

    def report_file_progress(self, file_index: int, total_files: int) -> None:
        pass


class _RecordingBackupReporter(AnalysisReporter):
    def __init__(self) -> None:
        self.entries: list[AnalyzedFileEntry] = []
        self.started = False
        self.summaries: list[BackupAnalysisSummary] = []
        self.progress: list[tuple[int, int]] = []

    def report_analysis_start(self) -> None:
        self.started = True

    def report(self, entry: AnalyzedFileEntry) -> None:
        self.entries.append(entry)

    def report_analysis_summary(self, summary: BackupAnalysisSummary) -> None:
        self.summaries.append(summary)

    def report_file_progress(self, file_index: int, total_files: int) -> None:
        self.progress.append((file_index, total_files))


@pytest.mark.asyncio
async def test_iterate_analyzed_entries_yields_analyzed_entries(tmp_path: Path) -> None:
    reporter = _CollectingReporter()
    async for entry in _iterate_analyzed_entries(
        tmp_path,
        file_reader=_ReaderStub(),
        analyzer=_AnalyzerStub(),
        db=_DbStub(),
    ):
        reporter.report(entry)

    assert len(reporter.entries) == 1
    reported = reporter.entries[0]
    assert reported.source_file.relative_path == Path("file.txt")
    assert reported.already_backed_up is True
    assert reported.backup_id == UUID("12345678-1234-5678-1234-567812345678")


@pytest.mark.asyncio
async def test_new_backup_with_reporter_reports_summary_and_progress(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.txt").write_bytes(b"alpha")
    (source / "b.txt").write_bytes(b"beta")

    backup_root = tmp_path / "backup"
    version = "ux1"

    db = CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=str(backup_root))))
    filestore = LocalFileStore(
        FilestoreConfig(
            backup_dir=str(backup_root),
            zip_enabled=False,
        )
    )

    recording = _RecordingBackupReporter()

    await new_backup(
        source,
        version,
        file_reader=LocalFileReader(path_filter=NullPathFilter()),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=filestore,
        reporter=recording,
    )

    assert recording.started is True
    assert len(recording.entries) == 2
    assert {e.source_file.relative_path for e in recording.entries} == {
        Path("a.txt"),
        Path("b.txt"),
    }
    assert len(recording.summaries) == 1
    s = recording.summaries[0]
    assert s.version_name == version
    assert s.num_files == 2
    assert s.files_to_backup == 2
    assert s.total_file_size == 9
    assert recording.progress == [(0, 2), (1, 2)]


@pytest.mark.asyncio
async def test_backup_progress_throttled_when_just_over_hundred_files(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for i in range(101):
        (source / f"f{i:03d}.txt").write_bytes(b"x")

    backup_root = tmp_path / "backup"
    version = "v101"

    db = CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=str(backup_root))))
    filestore = LocalFileStore(
        FilestoreConfig(
            backup_dir=str(backup_root),
            zip_enabled=False,
        )
    )
    recording = _RecordingBackupReporter()

    await new_backup(
        source,
        version,
        file_reader=LocalFileReader(path_filter=NullPathFilter()),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=filestore,
        reporter=recording,
    )

    assert recording.summaries[0].num_files == 101
    # progress_step = ceil(101/100) == 2 → indices 0, 2, …, 100 → 51 reports
    assert len(recording.progress) == 51
    assert recording.progress[0] == (0, 101)
    assert recording.progress[-1] == (100, 101)


@pytest.mark.asyncio
async def test_add_version_marks_version_completed_on_success(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "file.txt").write_text("payload", encoding="utf-8")
    db = _DbStub()

    await add_version(
        source,
        "v-complete",
        file_reader=_ReaderStub(),
        analyzer=_AnalyzerStub(),
        db=db,
        filestore=LocalFileStore(
            FilestoreConfig(backup_dir=str(tmp_path / "backup"), zip_enabled=False)
        ),
        reporter=_CollectingReporter(),
    )

    assert db.completed_versions == ["v-complete"]


@pytest.mark.asyncio
async def test_add_version_does_not_mark_version_completed_on_failure(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "file.txt").write_text("payload", encoding="utf-8")
    db = _DbStub(fail_on_add_file=True)

    with pytest.raises(RuntimeError, match="simulated write failure"):
        await add_version(
            source,
            "v-fail",
            file_reader=_ReaderStub(),
            analyzer=_AnalyzerStub(),
            db=db,
            filestore=LocalFileStore(
                FilestoreConfig(backup_dir=str(tmp_path / "backup"), zip_enabled=False)
            ),
            reporter=_CollectingReporter(),
        )

    assert db.completed_versions == []
