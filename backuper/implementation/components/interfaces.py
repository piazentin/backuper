import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, List, Optional
from pathlib import Path
from uuid import UUID


@dataclass
class FileEntry:
    path: Path
    relative_path: Path
    size: int
    mtime: float
    is_directory: bool = False
    hash: Optional[str] = None


@dataclass
class AnalyzedFileEntry:
    """Contains analysis results for a file"""

    source_file: FileEntry  # The original file entry
    hash: Optional[str] = None
    already_backed_up: bool = False
    backup_id: Optional[UUID] = None  # Will contain UUID if already backed up


@dataclass
class BackupedFileEntry:
    """Contains backup-specific information for a file"""

    source_file: FileEntry  # The original file entry
    backup_id: UUID  # Required unique backup ID
    stored_location: str  # Location where the file is stored
    is_compressed: bool  # Whether the file is compressed
    hash: str


class FileReader(ABC):
    @abstractmethod
    async def read_directory(self, path: Path) -> AsyncIterator[FileEntry]:
        pass


class BackupAnalyzer(ABC):
    @abstractmethod
    async def analyze_stream(
        self, entries: AsyncIterator[FileEntry], backup_database: "BackupDatabase"
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
    async def list_versions(self) -> List[str]:
        """List all backup version names"""
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
    async def get_files_by_hash(self, hash: str) -> List[BackupedFileEntry]:
        """Get file entries by their hash value"""
        pass

    @abstractmethod
    async def get_files_by_metadata(
        self, relative_path: Path, mtime: float, size: int
    ) -> List[BackupedFileEntry]:
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
        pass

    @abstractmethod
    def put(
        self,
        origin_file: os.PathLike[str],
        restore_path: Path,
        precomputed_hash: Optional[str] = None,
    ) -> PutResult:
        pass


@dataclass(frozen=True)
class BackupCheckVersion:
    name: str


@dataclass(frozen=True)
class BackupCheckFile:
    restore_path: str
    sha1hash: str
    stored_location: str


class BackupCheckDatabase(ABC):
    @abstractmethod
    def get_all_versions(self) -> List[BackupCheckVersion]:
        pass

    @abstractmethod
    def get_version_by_name(self, name: str) -> BackupCheckVersion:
        """Raises RuntimeError when the named version is missing."""
        pass

    @abstractmethod
    def get_files_for_version(
        self, version: BackupCheckVersion
    ) -> List[BackupCheckFile]:
        pass
