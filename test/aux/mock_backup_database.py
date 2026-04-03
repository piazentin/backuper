from collections.abc import AsyncIterator
from pathlib import Path

from backuper.interfaces import (
    BackupDatabase,
    BackupedFileEntry,
    FileEntry,
)


class MockBackupDatabase(BackupDatabase):
    """Mock backup database that returns predefined results"""

    def __init__(
        self,
        files_by_metadata: dict[tuple[str, int, float], BackupedFileEntry] = None,
        files_by_hash: dict[str, list[BackupedFileEntry]] = None,
    ):
        self.files_by_metadata = files_by_metadata or {}
        self.files_by_hash = files_by_hash or {}

    async def list_versions(self) -> list[str]:
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

    async def get_files_by_hash(self, hash: str) -> list[BackupedFileEntry]:
        return self.files_by_hash.get(hash, [])

    async def get_files_by_metadata(
        self, relative_path: Path, mtime: float, size: int
    ) -> list[BackupedFileEntry]:
        key = (str(relative_path), size, mtime)
        result = self.files_by_metadata.get(key)
        return [result] if result else []
