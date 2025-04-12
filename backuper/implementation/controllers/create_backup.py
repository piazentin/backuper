from pathlib import Path
from backuper.implementation.components.interfaces import FileReader, BackupAnalyzer, BackupDatabase, AnalyzedFileEntry

class CreateBackupController:
    def __init__(self, file_reader: FileReader, analyzer: BackupAnalyzer, db: BackupDatabase):
        self._file_reader = file_reader
        self._analyzer = analyzer
        self._db = db

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
