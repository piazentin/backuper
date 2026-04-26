from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from .exceptions import (
    CliUsageError as CliUsageError,
)
from .exceptions import (
    DestinationLockContendedError as DestinationLockContendedError,
)
from .exceptions import (
    MalformedManifestRowError as MalformedManifestRowError,
)
from .exceptions import (
    RestorePathError as RestorePathError,
)
from .exceptions import (
    RestoreVersionNotFoundError as RestoreVersionNotFoundError,
)
from .exceptions import (
    UnreachableCommandError as UnreachableCommandError,
)
from .exceptions import (
    UserFacingError as UserFacingError,
)
from .exceptions import (
    VersionAlreadyExistsError as VersionAlreadyExistsError,
)
from .exceptions import (
    VersionNotFoundError as VersionNotFoundError,
)


@dataclass(frozen=True)
class FileEntry:
    path: Path
    relative_path: Path
    size: int
    mtime: float
    is_directory: bool = False
    hash: str | None = None
    is_compressed: bool = False
    stored_location: str | None = None


@dataclass(frozen=True)
class AnalyzedFileEntry:
    """Contains analysis results for a file"""

    source_file: FileEntry  # The original file entry
    hash: str | None = None
    already_backed_up: bool = False
    backup_id: UUID | None = None  # Will contain UUID if already backed up


@dataclass(frozen=True)
class BackedUpFileEntry:
    """Contains backup-specific information for a file"""

    source_file: FileEntry  # The original file entry
    backup_id: UUID  # Required unique backup ID
    stored_location: str
    is_compressed: bool  # Whether the file is compressed
    hash: str


@dataclass(frozen=True)
class BackupAnalysisSummary:
    """Aggregated counts after analyzing a source tree for a backup run.

    Semantics match :class:`BackupAnalysisSummaryAccumulator` (one pass over
    analyzed entries). ``num_files``, ``total_file_size``, and ``files_to_backup``
    count **non-directory** entries only; ``num_directories`` counts directory
    entries.
    """

    version_name: str
    num_directories: int
    num_files: int
    total_file_size: int
    files_to_backup: int


@dataclass
class BackupAnalysisSummaryAccumulator:
    """Incremental builder for :class:`BackupAnalysisSummary` (streaming-friendly).

    Backup flows typically: stream :class:`AnalyzedFileEntry` in walk order and
    call :meth:`consume` for each entry, then emit exactly one
    ``report_analysis_summary(to_summary(...))`` before writing blobs and DB rows.
    File progress uses ``total_files == to_summary(...).num_files`` with **0-based**
    indices in the same walk order; avoid unknown-total reporter APIs and extra
    filesystem walks just to count files.
    """

    num_directories: int = 0
    num_files: int = 0
    total_file_size: int = 0
    files_to_backup: int = 0

    def consume(self, entry: AnalyzedFileEntry) -> None:
        if entry.source_file.is_directory:
            self.num_directories += 1
            return
        self.num_files += 1
        self.total_file_size += entry.source_file.size
        if not entry.already_backed_up:
            self.files_to_backup += 1

    def to_summary(self, version_name: str) -> BackupAnalysisSummary:
        return BackupAnalysisSummary(
            version_name=version_name,
            num_directories=self.num_directories,
            num_files=self.num_files,
            total_file_size=self.total_file_size,
            files_to_backup=self.files_to_backup,
        )


@dataclass(frozen=True)
class PutResult:
    restore_path: str
    hash: str
    stored_location: str
    is_compressed: bool
