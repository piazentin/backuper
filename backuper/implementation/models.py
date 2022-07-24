from dataclasses import dataclass
from typing import Union


@dataclass
class DirEntry:
    name: str


@dataclass
class FileEntry:
    name: str
    hash: str


FileSystemObject = Union[DirEntry, FileEntry]


@dataclass
class Version:
    name: str
