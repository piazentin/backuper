from pathlib import Path
from uuid import UUID

from backuper.components.reporter import StdoutAnalysisReporter
from backuper.models import AnalyzedFileEntry, FileEntry


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
