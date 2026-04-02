import os
from dataclasses import dataclass
from datetime import datetime
from operator import attrgetter

from backuper.legacy.implementation import utils


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
    backuped: bool


def _dir(
    absolute_dirname: os.PathLike, relative_dirname: os.PathLike, name: str
) -> Dir:
    return Dir(
        os.path.join(absolute_dirname, name), os.path.join(relative_dirname, name)
    )


def _file(
    backuped_hashes: set[str],
    absolute_dirname: os.PathLike,
    relative_dirname: os.PathLike,
    name: str,
) -> File:
    filepath = os.path.join(absolute_dirname, name)
    filestats = os.stat(filepath)
    hash = utils.compute_hash(filepath)

    return File(
        filepath,
        os.path.join(relative_dirname, name),
        hash=hash,
        size=filestats.st_size,
        last_modified_at=str(datetime.fromtimestamp(filestats.st_mtime)),
        last_access_at=str(datetime.fromtimestamp(filestats.st_atime)),
        backuped=hash in backuped_hashes,
    )


class Analyze:
    dirs: list[Dir] = []
    files: list[File] = []

    def __init__(self, backuped_hashes: set[str], path_to_analyze: os.PathLike) -> None:
        self.dirs = []
        self.files = []

        for dirpath, dirnames, filenames in os.walk(path_to_analyze, topdown=True):
            relative_path = utils.absolute_to_relative_path(path_to_analyze, dirpath)
            self.dirs.extend([_dir(dirpath, relative_path, dir) for dir in dirnames])
            self.files.extend(
                [
                    _file(backuped_hashes, dirpath, relative_path, file)
                    for file in filenames
                ]
            )

        self.dirs.sort(key=attrgetter("relative_path"))
        self.files.sort(key=attrgetter("relative_path"))
