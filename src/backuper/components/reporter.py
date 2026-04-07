from backuper.models import AnalyzedFileEntry
from backuper.ports import AnalysisReporter


class StdoutAnalysisReporter(AnalysisReporter):
    def report(self, entry: AnalyzedFileEntry) -> None:
        status = "Already backed up" if entry.already_backed_up else "New file"
        backup_id = f" (Backup ID: {entry.backup_id})" if entry.backup_id else ""
        print(f"{status}: {entry.source_file.relative_path}{backup_id}")
