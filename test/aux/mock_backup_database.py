from collections.abc import AsyncGenerator
from pathlib import Path

from backuper.models import BackedUpFileEntry, FileEntry
from backuper.ports import BackupDatabase


class MockBackupDatabase(BackupDatabase):
    """Mock backup database that returns predefined results"""

    def __init__(
        self,
        files_by_metadata: dict[
            tuple[str, int, float], BackedUpFileEntry | list[BackedUpFileEntry]
        ]
        | None = None,
        files_by_hash: dict[str, list[BackedUpFileEntry]] | None = None,
    ):
        self.files_by_metadata = {} if files_by_metadata is None else files_by_metadata
        self.files_by_hash = {} if files_by_hash is None else files_by_hash

    async def list_versions(self) -> list[str]:
        return ["test_version"]

    async def get_version_by_name(self, name: str) -> str:
        return name

    async def list_files(self, version: str) -> AsyncGenerator[FileEntry, None]:
        raise NotImplementedError("MockBackupDatabase.list_files is not used in tests")
        if False:  # pragma: no cover — async generator typing stub
            _p = Path()
            yield FileEntry(path=_p, relative_path=_p, size=0, mtime=0.0)

    async def create_version(self, version: str) -> None:
        # Not used in tests
        pass

    async def add_file(self, version: str, entry: BackedUpFileEntry) -> None:
        # Not used in tests
        pass

    async def get_files_by_hash(self, hash: str) -> list[BackedUpFileEntry]:
        return self.files_by_hash.get(hash, [])

    async def get_files_by_metadata(
        self, relative_path: Path, mtime: float, size: int
    ) -> list[BackedUpFileEntry]:
        key = (str(relative_path), size, mtime)
        result = self.files_by_metadata.get(key)
        if not result:
            return []
        if isinstance(result, list):
            return result
        return [result]
