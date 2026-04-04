from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


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
class BackupedFileEntry:
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


@dataclass
class BackupChunk:
    data: bytes
    metadata: dict
    compression: bool = False
    encryption: bool = False


class BackupStreamProcessor(ABC):
    @abstractmethod
    async def process_stream(
        self, entries: AsyncIterator[FileEntry]
    ) -> AsyncIterator[BackupChunk]:
        pass


class BackupWriter(ABC):
    @abstractmethod
    async def write_stream(self, chunks: AsyncIterator[BackupChunk]) -> None:
        pass


class BackupDatabase(ABC):
    @abstractmethod
    async def list_versions(self) -> list[str]:
        """List all backup version names"""
        pass

    @abstractmethod
    async def get_version_by_name(self, name: str) -> str:
        """Return the canonical version name. Raises RuntimeError when missing."""
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
    async def add_file(self, version: str, entry: BackupedFileEntry) -> None:
        """Add a file entry to a specific backup version"""
        pass

    @abstractmethod
    async def get_files_by_hash(self, hash: str) -> list[BackupedFileEntry]:
        """Get file entries by their hash value"""
        pass

    @abstractmethod
    async def get_files_by_metadata(
        self, relative_path: Path, mtime: float, size: int
    ) -> list[BackupedFileEntry]:
        """Get file entries by their metadata (relative path, mtime, and size)"""
        pass


class AnalysisReporter(ABC):
    @abstractmethod
    def report(self, entry: AnalyzedFileEntry) -> None:
        pass


@dataclass(frozen=True)
class PutResult:
    restore_path: str
    hash: str
    stored_location: str
    is_compressed: bool


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
