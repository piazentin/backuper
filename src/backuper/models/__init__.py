from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


class VersionNotFoundError(Exception):
    """Raised when a named backup version does not exist in the database."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Version not found: {name}")


@dataclass
class FileEntry:
    path: Path
    relative_path: Path
    size: int
    mtime: float
    is_directory: bool = False
    hash: str | None = None
    is_compressed: bool = False
    stored_location: str | None = None


@dataclass
class AnalyzedFileEntry:
    """Contains analysis results for a file"""

    source_file: FileEntry  # The original file entry
    hash: str | None = None
    already_backed_up: bool = False
    backup_id: UUID | None = None  # Will contain UUID if already backed up


@dataclass
class BackedUpFileEntry:
    """Contains backup-specific information for a file"""

    source_file: FileEntry  # The original file entry
    backup_id: UUID  # Required unique backup ID
    stored_location: str
    is_compressed: bool  # Whether the file is compressed
    hash: str


@dataclass(frozen=True)
class BackupAnalysisSummary:
    """Aggregated counts after analyzing a source tree for a backup run."""

    version_name: str
    num_directories: int
    num_files: int
    total_file_size: int
    files_to_backup: int


@dataclass(frozen=True)
class PutResult:
    restore_path: str
    hash: str
    stored_location: str
    is_compressed: bool
