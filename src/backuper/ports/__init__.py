from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path

from backuper.models import (
    AnalyzedFileEntry,
    BackedUpFileEntry,
    BackupAnalysisSummary,
    FileEntry,
    PutResult,
)


class FileReader(ABC):
    @abstractmethod
    async def read_directory(self, path: Path) -> AsyncIterator[FileEntry]:
        pass


class BackupAnalyzer(ABC):
    @abstractmethod
    async def analyze_stream(
        self, entries: AsyncIterator[FileEntry], backup_database: BackupDatabase
    ) -> AsyncIterator[AnalyzedFileEntry]:
        pass


class BackupDatabase(ABC):
    @abstractmethod
    async def list_versions(self) -> list[str]:
        """List all backup version names"""
        pass

    @abstractmethod
    async def get_version_by_name(self, name: str) -> str:
        """Return the canonical version name. Raises VersionNotFoundError when missing."""
        pass

    @abstractmethod
    async def list_files(self, version: str) -> AsyncIterator[FileEntry]:
        """List all files in a specific backup version"""
        pass

    @abstractmethod
    async def create_version(self, version: str) -> None:
        """Create a new backup version"""
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
