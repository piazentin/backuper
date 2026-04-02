from pathlib import Path
from uuid import uuid4

from backuper.implementation.components.interfaces import (
    AnalyzedFileEntry,
    AnalysisReporter,
    BackupAnalyzer,
    BackupDatabase,
    BackupedFileEntry,
    FileReader,
    FileStore,
)


async def _analyze_path(
    path: Path,
    *,
    file_reader: FileReader,
    analyzer: BackupAnalyzer,
    db: BackupDatabase,
    reporter: AnalysisReporter,
) -> None:
    """Analyze a path and print analyzed file entries."""
    file_entries = file_reader.read_directory(path)
    analyzed_entries = analyzer.analyze_stream(file_entries, db)

    async for entry in analyzed_entries:
        reporter.report(entry)


async def new_backup(
    source: Path,
    version: str,
    *,
    file_reader: FileReader,
    analyzer: BackupAnalyzer,
    db: BackupDatabase,
    filestore: FileStore,
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
    )


async def add_version(
    source: Path,
    version: str,
    *,
    file_reader: FileReader,
    analyzer: BackupAnalyzer,
    db: BackupDatabase,
    filestore: FileStore,
) -> None:
    versions = await db.list_versions()
    if version in versions:
        raise ValueError(f"There is already a backup versioned with the name {version}")
    await db.create_version(version)
    await _run_backup_stream(
        source,
        version,
        file_reader=file_reader,
        analyzer=analyzer,
        db=db,
        filestore=filestore,
    )


async def _run_backup_stream(
    source: Path,
    version: str,
    *,
    file_reader: FileReader,
    analyzer: BackupAnalyzer,
    db: BackupDatabase,
    filestore: FileStore,
) -> None:
    file_entries = file_reader.read_directory(source)
    analyzed_entries = analyzer.analyze_stream(file_entries, db)

    async for entry in analyzed_entries:
        backup_entry = await _to_backuped_entry(entry, db=db, filestore=filestore)
        await db.add_file(version, backup_entry)


async def _to_backuped_entry(
    entry: AnalyzedFileEntry,
    *,
    db: BackupDatabase,
    filestore: FileStore,
) -> BackupedFileEntry:
    source_file = entry.source_file

    if source_file.is_directory:
        return BackupedFileEntry(
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
            return BackupedFileEntry(
                source_file=source_file,
                backup_id=matched.backup_id,
                stored_location=matched.stored_location,
                is_compressed=matched.is_compressed,
                hash=matched.hash,
            )

    stored = filestore.put(source_file.path, source_file.relative_path, entry.hash)
    return BackupedFileEntry(
        source_file=source_file,
        backup_id=uuid4(),
        stored_location=stored.stored_location,
        is_compressed=stored.is_compressed,
        hash=stored.hash,
    )
