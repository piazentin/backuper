from collections.abc import AsyncIterator

from backuper.interfaces import (
    AnalyzedFileEntry,
    BackupAnalyzer,
    BackupDatabase,
    FileEntry,
)
from backuper.utils.hashing import compute_hash


class BackupAnalyzerImpl(BackupAnalyzer):
    def __init__(self):
        pass

    async def analyze_stream(
        self, file_stream: AsyncIterator[FileEntry], db: BackupDatabase
    ) -> AsyncIterator[AnalyzedFileEntry]:
        """Analyze a stream of files and determine which need to be backed up"""

        async for file_entry in file_stream:
            already_backed_up = False
            backup_id = None
            file_hash = None

            # Skip directories - they don't need content analysis
            if file_entry.is_directory:
                yield AnalyzedFileEntry(
                    source_file=file_entry,
                    already_backed_up=False,
                    backup_id=None,
                    hash=None,
                )
                continue

            # First check if there's a match based on path, size and mtime
            stored_files = await db.get_files_by_metadata(
                file_entry.relative_path, file_entry.mtime, file_entry.size
            )
            if stored_files:
                stored_file = stored_files[0]  # Use the first match
                already_backed_up = True
                backup_id = stored_file.backup_id
                file_hash = stored_file.hash

            # If no match found, compute hash and check for content match
            if not already_backed_up:
                file_hash = compute_hash(file_entry.path)
                stored_files = await db.get_files_by_hash(file_hash)
                if stored_files:
                    stored_file = stored_files[0]  # Use the first match
                    already_backed_up = True
                    backup_id = stored_file.backup_id

            yield AnalyzedFileEntry(
                source_file=file_entry,
                already_backed_up=already_backed_up,
                backup_id=backup_id,
                hash=file_hash,
            )
