import os
from pathlib import Path
from typing import AsyncIterator

from backuper.implementation.components.interfaces import FileEntry, FileReader


class LocalFileReader(FileReader):
    async def read_directory(self, path: Path) -> AsyncIterator[FileEntry]:
        for root, dirs, files in os.walk(path):
            root_path = Path(root)

            # Yield entries for directories
            for dir_name in dirs:
                dir_path = root_path / dir_name
                relative_path = dir_path.relative_to(path)
                mtime = os.path.getmtime(dir_path)

                yield FileEntry(
                    path=dir_path,
                    relative_path=relative_path,
                    size=0,  # Directories have size 0
                    mtime=mtime,
                    is_directory=True,
                )

            # Yield entries for files
            for file in files:
                file_path = root_path / file
                relative_path = file_path.relative_to(path)
                size = os.path.getsize(file_path)
                mtime = os.path.getmtime(file_path)

                yield FileEntry(
                    path=file_path,
                    relative_path=relative_path,
                    size=size,
                    mtime=mtime,
                    is_directory=False,
                )
