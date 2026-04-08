from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

from backuper.models import (
    AnalyzedFileEntry,
    BackedUpFileEntry,
    BackupAnalysisSummary,
    VersionAlreadyExistsError,
)
from backuper.ports import (
    AnalysisReporter,
    BackupAnalyzer,
    BackupDatabase,
    FileReader,
    FileStore,
)


async def _iterate_analyzed_entries(
    source: Path,
    *,
    file_reader: FileReader,
    analyzer: BackupAnalyzer,
    db: BackupDatabase,
) -> AsyncIterator[AnalyzedFileEntry]:
    file_entries = file_reader.read_directory(source)
    analyzed_entries = analyzer.analyze_stream(file_entries, db)
    async for entry in analyzed_entries:
        yield entry


async def new_backup(
    source: Path,
    version: str,
    *,
    file_reader: FileReader,
    analyzer: BackupAnalyzer,
    db: BackupDatabase,
    filestore: FileStore,
    reporter: AnalysisReporter,
) -> None:
    versions = await db.list_versions()
    if version not in versions:
        await db.create_version(version)
    await _run_backup_stream(
        source,
        version,
        file_reader=file_reader,
        analyzer=analyzer,
        db=db,
        filestore=filestore,
        reporter=reporter,
    )


async def add_version(
    source: Path,
    version: str,
    *,
    file_reader: FileReader,
    analyzer: BackupAnalyzer,
    db: BackupDatabase,
    filestore: FileStore,
    reporter: AnalysisReporter,
) -> None:
    versions = await db.list_versions()
    if version in versions:
        raise VersionAlreadyExistsError(version)
    await db.create_version(version)
    await _run_backup_stream(
        source,
        version,
        file_reader=file_reader,
        analyzer=analyzer,
        db=db,
        filestore=filestore,
        reporter=reporter,
    )


def _backup_analysis_summary(
    analyzed: list[AnalyzedFileEntry], version: str
) -> BackupAnalysisSummary:
    file_entries = [e for e in analyzed if not e.source_file.is_directory]
    return BackupAnalysisSummary(
        version_name=version,
        num_directories=sum(1 for e in analyzed if e.source_file.is_directory),
        num_files=len(file_entries),
        total_file_size=sum(e.source_file.size for e in file_entries),
        files_to_backup=sum(1 for e in file_entries if not e.already_backed_up),
    )


async def _collect_analyzed_entries(
    source: Path,
    *,
    file_reader: FileReader,
    analyzer: BackupAnalyzer,
    db: BackupDatabase,
) -> list[AnalyzedFileEntry]:
    return [
        entry
        async for entry in _iterate_analyzed_entries(
            source, file_reader=file_reader, analyzer=analyzer, db=db
        )
    ]


async def _run_backup_stream(
    source: Path,
    version: str,
    *,
    file_reader: FileReader,
    analyzer: BackupAnalyzer,
    db: BackupDatabase,
    filestore: FileStore,
    reporter: AnalysisReporter,
) -> None:
    analyzed_list = await _collect_analyzed_entries(
        source, file_reader=file_reader, analyzer=analyzer, db=db
    )
    reporter.report_analysis_summary(_backup_analysis_summary(analyzed_list, version))

    total_files = sum(1 for e in analyzed_list if not e.source_file.is_directory)
    one_percent = int(max(1, total_files / 100))

    file_idx = 0
    for entry in analyzed_list:
        if not entry.source_file.is_directory:
            if file_idx % one_percent == 0:
                reporter.report_file_progress(file_idx, total_files)
            file_idx += 1
        backup_entry = await _to_backed_up_entry(entry, db=db, filestore=filestore)
        await db.add_file(version, backup_entry)


async def _to_backed_up_entry(
    entry: AnalyzedFileEntry,
    *,
    db: BackupDatabase,
    filestore: FileStore,
) -> BackedUpFileEntry:
    source_file = entry.source_file

    if source_file.is_directory:
        return BackedUpFileEntry(
            source_file=source_file,
            backup_id=uuid4(),
            stored_location="",
            is_compressed=False,
            hash="",
        )

    if entry.already_backed_up and entry.hash:
        matches = await db.get_files_by_hash(entry.hash)
        if matches:
            matched = matches[0]
            return BackedUpFileEntry(
                source_file=source_file,
                backup_id=matched.backup_id,
                stored_location=matched.stored_location,
                is_compressed=matched.is_compressed,
                hash=matched.hash,
            )

    stored = filestore.put(source_file.path, source_file.relative_path, entry.hash)
    return BackedUpFileEntry(
        source_file=source_file,
        backup_id=uuid4(),
        stored_location=stored.stored_location,
        is_compressed=stored.is_compressed,
        hash=stored.hash,
    )
