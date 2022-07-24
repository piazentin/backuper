from dataclasses import dataclass
from typing import Union

from backuper.implementation import utils


@dataclass
class DirEntry:
    name: str

    def normalized_path(self) -> str:
        return utils.normalize_path(self.name)


@dataclass
class FileEntry:
    name: str
    hash: str

    def normalized_path(self) -> str:
        return utils.normalize_path(self.name)


FileSystemObject = Union[DirEntry, FileEntry]


@dataclass
class Version:
    name: str
