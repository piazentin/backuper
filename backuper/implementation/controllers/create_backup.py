from pathlib import Path
from uuid import uuid4
from backuper.implementation.components.interfaces import (
    FileReader,
    BackupAnalyzer,
    BackupDatabase,
    AnalyzedFileEntry,
    BackupedFileEntry,
)
from backuper.implementation.components.filestore import LocalFileStore


class CreateBackupController:
    def __init__(
        self,
        file_reader: FileReader,
        analyzer: BackupAnalyzer,
        db: BackupDatabase,
        filestore: LocalFileStore,
    ):
        self._file_reader = file_reader
        self._analyzer = analyzer
        self._db = db
        self._filestore = filestore

    async def analyze_path(self, path: Path) -> None:
        """Analyze a path and print analyzed file entries"""
        # Get file entries from reader
        file_entries = self._file_reader.read_directory(path)

        # Analyze the entries
        analyzed_entries = self._analyzer.analyze_stream(file_entries, self._db)

        # Print each analyzed entry
        async for entry in analyzed_entries:
            status = "Already backed up" if entry.already_backed_up else "New file"
            backup_id = f" (Backup ID: {entry.backup_id})" if entry.backup_id else ""
            print(f"{status}: {entry.source_file.relative_path}{backup_id}")

    async def create_backup(self, source: Path, version: str) -> None:
        versions = await self._db.list_versions()
        if version not in versions:
            await self._db.create_version(version)

        file_entries = self._file_reader.read_directory(source)
        analyzed_entries = self._analyzer.analyze_stream(file_entries, self._db)

        async for entry in analyzed_entries:
            backup_entry = await self._to_backuped_entry(entry)
            await self._db.add_file(version, backup_entry)

    async def _to_backuped_entry(self, entry: AnalyzedFileEntry) -> BackupedFileEntry:
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
            matches = await self._db.get_files_by_hash(entry.hash)
            if matches:
                matched = matches[0]
                return BackupedFileEntry(
                    source_file=source_file,
                    backup_id=matched.backup_id,
                    stored_location=matched.stored_location,
                    is_compressed=matched.is_compressed,
                    hash=matched.hash,
                )

        stored = self._filestore.put(source_file.path, source_file.relative_path, entry.hash)
        return BackupedFileEntry(
            source_file=source_file,
            backup_id=uuid4(),
            stored_location=stored.stored_location,
            is_compressed=stored.is_compressed,
            hash=stored.hash,
        )
