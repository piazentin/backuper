from typing import AsyncIterator, List, Dict, Union, Tuple
from pathlib import Path
from backuper.implementation.interfaces import (
    BackupDatabase,
    FileEntry,
    BackupedFileEntry,
)


class MockBackupDatabase(BackupDatabase):
    """Mock backup database that returns predefined results"""

    def __init__(
        self,
        files_by_metadata: Dict[Tuple[str, int, float], BackupedFileEntry] = None,
        files_by_hash: Dict[str, List[BackupedFileEntry]] = None,
    ):
        self.files_by_metadata = files_by_metadata or {}
        self.files_by_hash = files_by_hash or {}

    async def list_versions(self) -> List[str]:
        return ["test_version"]

    async def get_version_by_name(self, name: str) -> str:
        return name

    async def list_files(self, version: str) -> AsyncIterator[FileEntry]:
        # Not used in tests
        pass

    async def create_version(self, version: str) -> None:
        # Not used in tests
        pass

    async def add_file(self, version: str, entry: BackupedFileEntry) -> None:
        # Not used in tests
        pass

    async def get_files_by_hash(self, hash: str) -> List[BackupedFileEntry]:
        return self.files_by_hash.get(hash, [])

    async def get_files_by_metadata(
        self, relative_path: Path, mtime: float, size: int
    ) -> List[BackupedFileEntry]:
        key = (str(relative_path), size, mtime)
        result = self.files_by_metadata.get(key)
        return [result] if result else []
