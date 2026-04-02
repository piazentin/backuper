from typing import AsyncIterator, List
from pathlib import Path
from backuper.implementation.interfaces import FileReader, FileEntry


class MockFileReader(FileReader):
    """Mock file reader that returns a predefined stream of file entries"""

    def __init__(self, entries: List[FileEntry]):
        self.entries = entries

    async def read_directory(self, path: Path) -> AsyncIterator[FileEntry]:
        for entry in self.entries:
            yield entry
