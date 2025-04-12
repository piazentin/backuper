from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional
from pathlib import Path

@dataclass
class FileEntry:
    path: Path
    relative_path: Path
    size: int
    mtime: float
    is_directory: bool = False
    hash: Optional[str] = None
    content: Optional[bytes] = None

class FileReader(ABC):
    @abstractmethod
    async def read_directory(self, path: Path) -> AsyncIterator[FileEntry]:
        pass

class BackupAnalyzer(ABC):
    @abstractmethod
    async def analyze_stream(self, entries: AsyncIterator[FileEntry]) -> AsyncIterator[FileEntry]:
        pass

@dataclass
class BackupChunk:
    data: bytes
    metadata: dict
    compression: bool = False
    encryption: bool = False

class BackupStreamProcessor(ABC):
    @abstractmethod
    async def process_stream(self, entries: AsyncIterator[FileEntry]) -> AsyncIterator[BackupChunk]:
        pass

class BackupWriter(ABC):
    @abstractmethod
    async def write_stream(self, chunks: AsyncIterator[BackupChunk]) -> None:
        pass
