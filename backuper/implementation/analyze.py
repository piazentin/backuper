from dataclasses import dataclass
from datetime import datetime
from operator import attrgetter
import os
from typing import List

from backuper.implementation import utils


@dataclass
class Dir:
    absolute_path: os.PathLike
    relative_path: os.PathLike


@dataclass
class File:
    absolute_path: os.PathLike
    relative_path: os.PathLike
    hash: str
    size: int
    last_modified_at: str
    last_access_at: str


def _dir(
    absolute_dirname: os.PathLike, relative_dirname: os.PathLike, name: str
) -> Dir:
    return Dir(
        os.path.join(absolute_dirname, name), os.path.join(relative_dirname, name)
    )


def _file(
    absolute_dirname: os.PathLike, relative_dirname: os.PathLike, name: str
) -> File:
    filepath = os.path.join(absolute_dirname, name)
    filestats = os.stat(filepath)

    return File(
        filepath,
        os.path.join(relative_dirname, name),
        utils.compute_hash(filepath),
        size=filestats.st_size,
        last_modified_at=str(datetime.fromtimestamp(filestats.st_mtime)),
        last_access_at=str(datetime.fromtimestamp(filestats.st_atime)),
    )


class Analyze:
    dirs: List[Dir] = []
    files: List[File] = []

    def __init__(self, path_to_analyze: os.PathLike) -> None:
        self.dirs = []
        self.files = []

        for dirpath, dirnames, filenames in os.walk(path_to_analyze, topdown=True):
            relative_path = utils.absolute_to_relative_path(path_to_analyze, dirpath)
            self.dirs.extend([_dir(dirpath, relative_path, dir) for dir in dirnames])
            self.files.extend(
                [_file(dirpath, relative_path, file) for file in filenames]
            )
        self.dirs.sort(key=attrgetter("relative_path"))
        self.files.sort(key=attrgetter("relative_path"))
