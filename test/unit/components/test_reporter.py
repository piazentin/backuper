from pathlib import Path
from uuid import UUID

from backuper.components.reporter import StdoutAnalysisReporter
from backuper.models import AnalyzedFileEntry, BackupAnalysisSummary, FileEntry


def test_stdout_analysis_reporter_prints_expected_message(capsys) -> None:
    reporter = StdoutAnalysisReporter()
    entry = AnalyzedFileEntry(
        source_file=FileEntry(
            path=Path("/src/file.txt"),
            relative_path=Path("file.txt"),
            size=10,
            mtime=100.0,
            is_directory=False,
        ),
        hash="abc123",
        already_backed_up=True,
        backup_id=UUID("12345678-1234-5678-1234-567812345678"),
    )

    reporter.report(entry)

    assert (
        capsys.readouterr().out
        == "Already backed up: file.txt (Backup ID: 12345678-1234-5678-1234-567812345678)\n"
    )


def test_stdout_analysis_reporter_prints_new_directory(capsys) -> None:
    reporter = StdoutAnalysisReporter()
    entry = AnalyzedFileEntry(
        source_file=FileEntry(
            path=Path("/src/subdir"),
            relative_path=Path("subdir"),
            size=0,
            mtime=100.0,
            is_directory=True,
        ),
        hash="",
        already_backed_up=False,
        backup_id=None,
    )
    reporter.report(entry)
    assert capsys.readouterr().out == "New directory: subdir\n"


def test_stdout_analysis_reporter_prints_backed_up_directory(capsys) -> None:
    reporter = StdoutAnalysisReporter()
    entry = AnalyzedFileEntry(
        source_file=FileEntry(
            path=Path("/src/subdir"),
            relative_path=Path("subdir"),
            size=0,
            mtime=100.0,
            is_directory=True,
        ),
        hash="",
        already_backed_up=True,
        backup_id=UUID("12345678-1234-5678-1234-567812345678"),
    )
    reporter.report(entry)
    assert (
        capsys.readouterr().out
        == "Already backed up directory: subdir (Backup ID: 12345678-1234-5678-1234-567812345678)\n"
    )


def test_stdout_analysis_reporter_prints_analysis_summary(capsys) -> None:
    reporter = StdoutAnalysisReporter()
    summary = BackupAnalysisSummary(
        version_name="v9",
        num_directories=1,
        num_files=2,
        total_file_size=42,
        files_to_backup=1,
    )

    reporter.report_analysis_summary(summary)

    out = capsys.readouterr().out
    assert "+++++ BACKUP ANALYSIS RESULT FOR VERSION v9 +++++" in out
    assert "Number of directories: 1" in out
    assert "Number of files: 2" in out
    assert "Total size of files: 42" in out
    assert "Files to backup: 1" in out


def test_stdout_analysis_reporter_prints_analysis_start(capsys) -> None:
    reporter = StdoutAnalysisReporter()
    reporter.report_analysis_start()
    assert capsys.readouterr().out == "Running analysis... This may take a while.\n"


def test_stdout_analysis_reporter_prints_file_progress(capsys) -> None:
    reporter = StdoutAnalysisReporter()
    reporter.report_file_progress(1, 4)
    assert capsys.readouterr().out == "Processed 25% of files...\n"


def test_stdout_analysis_reporter_skips_progress_when_no_files(capsys) -> None:
    reporter = StdoutAnalysisReporter()
    reporter.report_file_progress(0, 0)
    assert capsys.readouterr().out == ""
