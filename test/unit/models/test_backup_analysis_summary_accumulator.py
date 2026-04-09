from pathlib import Path
from uuid import UUID

from backuper.models import (
    AnalyzedFileEntry,
    BackupAnalysisSummary,
    BackupAnalysisSummaryAccumulator,
    FileEntry,
)


def _file(rel: str, *, size: int = 1, mtime: float = 1.0) -> FileEntry:
    return FileEntry(
        path=Path("/x") / rel,
        relative_path=Path(rel),
        size=size,
        mtime=mtime,
        is_directory=False,
    )


def _dir(rel: str) -> FileEntry:
    return FileEntry(
        path=Path("/x") / rel,
        relative_path=Path(rel),
        size=0,
        mtime=1.0,
        is_directory=True,
    )


def test_accumulator_matches_backup_analysis_summary_semantics() -> None:
    analyzed = [
        AnalyzedFileEntry(source_file=_dir("d")),
        AnalyzedFileEntry(
            source_file=_file("a.txt", size=10),
            already_backed_up=False,
        ),
        AnalyzedFileEntry(
            source_file=_file("b.txt", size=20),
            hash="h",
            already_backed_up=True,
            backup_id=UUID("12345678-1234-5678-1234-567812345678"),
        ),
    ]
    acc = BackupAnalysisSummaryAccumulator()
    for e in analyzed:
        acc.consume(e)
    assert acc.to_summary("v1") == BackupAnalysisSummary(
        version_name="v1",
        num_directories=1,
        num_files=2,
        total_file_size=30,
        files_to_backup=1,
    )


def test_accumulator_empty_tree() -> None:
    acc = BackupAnalysisSummaryAccumulator()
    assert acc.to_summary("vx") == BackupAnalysisSummary(
        version_name="vx",
        num_directories=0,
        num_files=0,
        total_file_size=0,
        files_to_backup=0,
    )
