from collections.abc import AsyncIterator
from pathlib import Path

from backuper.models import FileEntry
from backuper.ports import FileReader


class MockFileReader(FileReader):
    """Mock file reader that returns a predefined stream of file entries"""

    def __init__(self, entries: list[FileEntry]):
        self.entries = entries

    async def read_directory(self, path: Path) -> AsyncIterator[FileEntry]:
        for entry in self.entries:
            yield entry
