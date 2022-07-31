from dataclasses import dataclass
from typing import Union

from backuper.implementation import utils

StoredLocation = str


@dataclass(frozen=True)
class DirEntry:
    name: str

    def normalized_path(self) -> str:
        return utils.normalize_path(self.name)


@dataclass
class Version:
    name: str


@dataclass(frozen=True)
class StoredFile:
    restore_path: str
    sha1hash: str
    stored_location: StoredLocation
    is_compressed: bool


FileSystemObject = Union[DirEntry, StoredFile]
