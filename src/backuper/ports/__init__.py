from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import AbstractContextManager
from pathlib import Path

from backuper.models import (
    AnalyzedFileEntry,
    BackedUpFileEntry,
    BackupAnalysisSummary,
    FileEntry,
    PutResult,
)
from backuper.models import (
    DestinationLockContendedError as DestinationLockContendedError,
)


class FileReader(ABC):
    @abstractmethod
    async def read_directory(self, path: Path) -> AsyncGenerator[FileEntry, None]:
        raise NotImplementedError
        if False:  # pragma: no cover — async generator typing stub
            _p = Path()
            yield FileEntry(path=_p, relative_path=_p, size=0, mtime=0.0)


class PathFilter(ABC):
    @abstractmethod
    def prepare_walk_directory(self, walk_root: Path, *, source_root: Path) -> None:
        """Prepare state for evaluating entries discovered in ``walk_root``."""
        pass

    @abstractmethod
    def allows(self, entry: FileEntry, *, source_root: Path) -> bool:
        """Return True when an entry should be included in traversal/output."""
        pass

    def exclusion_reason(self, entry: FileEntry, *, source_root: Path) -> str | None:
        """When ``allows`` is false, a short log-facing reason; ``None`` when included."""
        if self.allows(entry, source_root=source_root):
            return None
        return f"excluded by {self.__class__.__name__}"

    def can_prune_subtree(self, entry: FileEntry, *, source_root: Path) -> bool:
        """Return True when a rejected directory can be pruned from traversal."""
        return False


class BackupAnalyzer(ABC):
    @abstractmethod
    async def analyze_stream(
        self, entries: AsyncIterator[FileEntry], backup_database: BackupDatabase
    ) -> AsyncGenerator[AnalyzedFileEntry, None]:
        """Yield analyzed entries; metadata/hash ties use the first list element."""
        raise NotImplementedError
        if False:  # pragma: no cover — async generator typing stub
            _p = Path()
            _fe = FileEntry(path=_p, relative_path=_p, size=0, mtime=0.0)
            yield AnalyzedFileEntry(source_file=_fe)


class BackupDatabase(ABC):
    @abstractmethod
    async def list_versions(self) -> list[str]:
        """List all backup version names"""
        pass

    @abstractmethod
    async def most_recent_version(self) -> str | None:
        """Return the most recent completed backup version, or ``None`` when absent."""
        pass

    @abstractmethod
    async def get_version_by_name(self, name: str) -> str:
        """Return the canonical version name. Raises VersionNotFoundError when missing."""
        pass

    @abstractmethod
    async def list_files(self, version: str) -> AsyncGenerator[FileEntry, None]:
        """List all files in a specific backup version"""
        raise NotImplementedError
        if False:  # pragma: no cover — async generator typing stub
            _p = Path()
            yield FileEntry(path=_p, relative_path=_p, size=0, mtime=0.0)

    @abstractmethod
    async def create_version(self, version: str) -> None:
        """Create a new backup version"""
        pass

    @abstractmethod
    async def complete_version(self, version: str) -> None:
        """Mark a previously-created version as completed."""
        pass

    @abstractmethod
    async def add_file(self, version: str, entry: BackedUpFileEntry) -> None:
        """Add a file entry to a specific backup version"""
        pass

    @abstractmethod
    async def get_files_by_hash(self, hash: str) -> list[BackedUpFileEntry]:
        """Get file entries by their hash value"""
        pass

    @abstractmethod
    async def get_files_by_metadata(
        self, relative_path: Path, mtime: float, size: int
    ) -> list[BackedUpFileEntry]:
        """Get file entries by their metadata (relative path, mtime, and size)"""
        pass


class DestinationWriteLock(ABC):
    @abstractmethod
    def acquire(self, destination_root: Path) -> AbstractContextManager[None]:
        """Acquire a non-blocking exclusive writer lock for ``destination_root``.

        Implementations should fail fast when another active writer already holds
        the destination lock by raising ``DestinationLockContendedError``, and
        return a context manager that releases lock ownership on exit.
        """
        pass


class AnalysisReporter(ABC):
    @abstractmethod
    def report_analysis_start(self) -> None:
        """Exactly once per backup run: before the analysis leg starts."""

    @abstractmethod
    def report(self, entry: AnalyzedFileEntry) -> None:
        pass

    @abstractmethod
    def report_analysis_summary(self, summary: BackupAnalysisSummary) -> None:
        """Exactly once per backup run: after the analysis leg, before file progress."""

    @abstractmethod
    def report_file_progress(self, file_index: int, total_files: int) -> None:
        """Backup-leg progress for non-directory files in walk order.

        ``file_index`` is 0-based. ``total_files`` equals
        ``BackupAnalysisSummary.num_files`` for this run. Controllers throttle
        calls (e.g. about once per 1% of files); implementations may no-op some
        invocations.
        """


class FileStore(ABC):
    @abstractmethod
    def exists(self, stored_location: str) -> bool:
        """Return True if the blob exists at this path under the backup data directory."""
        pass

    @abstractmethod
    def blob_relative_path(self, file_hash: str, is_compressed: bool) -> str:
        """Path segments under the backup data directory for this content hash."""
        pass

    @abstractmethod
    def blob_exists(self, file_hash: str, is_compressed: bool) -> bool:
        pass

    @abstractmethod
    def read_blob(self, file_hash: str, is_compressed: bool) -> bytes:
        """Raw bytes for an uncompressed blob, or extracted payload for a zip blob."""
        pass

    @abstractmethod
    def put(
        self,
        origin_file: os.PathLike[str],
        restore_path: Path,
        precomputed_hash: str | None = None,
    ) -> PutResult:
        pass
