from backuper.models import AnalyzedFileEntry, BackupAnalysisSummary
from backuper.ports import AnalysisReporter


class NoOpAnalysisReporter(AnalysisReporter):
    """Silent reporter for tests and non-interactive callers."""

    def report_analysis_start(self) -> None:
        pass

    def report(self, entry: AnalyzedFileEntry) -> None:
        pass

    def report_analysis_summary(self, summary: BackupAnalysisSummary) -> None:
        pass

    def report_file_progress(self, file_index: int, total_files: int) -> None:
        pass


class StdoutAnalysisReporter(AnalysisReporter):
    def report_analysis_start(self) -> None:
        print("Running analysis... This may take a while.")

    def report(self, entry: AnalyzedFileEntry) -> None:
        if entry.source_file.is_directory:
            status = (
                "Already backed up directory"
                if entry.already_backed_up
                else "New directory"
            )
        else:
            status = "Already backed up" if entry.already_backed_up else "New file"
        backup_id = f" (Backup ID: {entry.backup_id})" if entry.backup_id else ""
        print(f"{status}: {entry.source_file.relative_path}{backup_id}")

    def report_analysis_summary(self, summary: BackupAnalysisSummary) -> None:
        title_str = (
            f"+++++ BACKUP ANALYSIS RESULT FOR VERSION {summary.version_name} +++++"
        )
        print(title_str)
        print(f"Number of directories: {summary.num_directories}")
        print(f"Number of files: {summary.num_files}")
        print(f"Total size of files: {summary.total_file_size}")
        print(f"Files to backup: {summary.files_to_backup}")
        print("+" * len(title_str))

    def report_file_progress(self, file_index: int, total_files: int) -> None:
        if total_files == 0:
            return
        print(f"Processed {format((file_index / total_files), '.0%')} of files...")
