from genericpath import isfile
import hashlib
import os
import shutil
import csv
from sys import path
from abc import ABC

from typing import Iterator, List, IO, Union
from dataclasses import dataclass

import backuper.commands as commands


@dataclass
class DirEntry:
    name: str


@dataclass
class FileEntry:
    name: str
    hash: str


class MetaFileHandler(ABC):
    destination: str
    name: str
    is_open: bool

    _filename: str
    _file: IO

    def __init__(self, destination: str, name: str) -> None:
        self.destination = destination
        self.name = name
        self._filename = os.path.join(destination, name + '.csv')
        self.is_open = False

    def _open(self, open_mode):
        if not self.is_open:
            self._file = open(self._filename, open_mode)
            self.is_open = True
        return self

    def __exit__(self, *_) -> None:
        if self.is_open:
            self._file.close()
            self.is_open = False


class MetaWriter(MetaFileHandler):
    def __enter__(self) -> 'MetaWriter':
        return self._open('x')

    def add_dir(self, dirname: str) -> None:
        if not self.is_open:
            raise ValueError('Meta is not open for writing')
        self._file.write(f'"d","{dirname}",""\n')

    def add_file(self, filename: str, hash: str) -> None:
        if not self.is_open:
            raise ValueError('Meta is not open for writing')
        self._file.write(f'"f","{filename}","{hash}"\n')


class MetaReader(MetaFileHandler):
    def __enter__(self) -> 'MetaReader':
        self._open('r')

    def entries(self) -> Iterator[Union[DirEntry, FileEntry]]:
        for row in csv.reader(self._file, delimiter=',', quotechar='"'):
            if row[0] == 'd':
                yield DirEntry(row[1])
            elif row[1] == 'f':
                yield FileEntry(row[1], row[2])

    def file_entries(self) -> Iterator[FileEntry]:
        for entry in self.entries():
            if isinstance(entry, FileEntry):
                yield entry


def _to_relative_path(root: str, path: str) -> str:
    return path[len(root):]


def _process_dirs(snapshot_meta: MetaWriter, relative_path: str, dirs: List[str]) -> None:
    for dir in dirs:
        dirname = os.path.join(relative_path, dir)
        snapshot_meta.add_dir(dirname)


def sha1_hash(filename: str) -> str:
    BUF_SIZE = 65536  # 64kb
    sha1 = hashlib.sha1()
    with open(filename, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()


def _process_files(meta_writer: MetaWriter, full_path: str, relative_path: str, destination_dirname: str, filenames: List[str]) -> None:
    for filename in filenames:
        relative_filename = os.path.join(relative_path, filename)
        full_filename = os.path.join(full_path, filename)

        hash = sha1_hash(full_filename)
        destination_filename = os.path.join(destination_dirname, 'data', hash)
        if not os.path.isfile(destination_filename):
            shutil.copyfile(full_filename, destination_filename)
        meta_writer.add_file(relative_filename, hash)


def _initialize(path: str) -> None:
    os.makedirs(path)
    os.mkdir(os.path.join(path, 'data'))


def _process_backup(meta_writer: MetaWriter, source: str, destination: str) -> None:
    with meta_writer:
        for dirpath, dirnames, filenames in os.walk(source, topdown=True):
            relative_path = _to_relative_path(source, dirpath)
            print(f'Processing "{relative_path}"...')
            _process_dirs(meta_writer, relative_path, dirnames)
            _process_files(meta_writer, dirpath,
                           relative_path, destination, filenames)


def _metas_to_check(command: commands.CheckCommand) -> List[MetaReader]:
    if command.name:
        [MetaReader(command.destination, command.name, 'r')]
    else:
        [MetaReader(command.destination, command.name, 'r')
         for n in os.listdir(command.destination) if n.endswith('.csv')]


def _check_missing_hashes(meta: MetaReader) -> List[str]:
    errors = []
    with meta:
        for entry in meta.file_entries():
            hash_filename = os.path.join(meta.destination, 'data', entry.hash)
            if not os.path.exists(hash_filename):
                errors.append(
                    f'[{meta.name}] Missing hash {entry.hash} for {entry.name}')
    return errors


def new(command: commands.NewCommand) -> None:
    if not os.path.exists(command.source):
        raise ValueError(f'source path {command.source} does not exists')
    if os.path.exists(command.destination):
        raise ValueError(
            f'destination path {command.destination} already exists')

    print(
        f'Creating new backup from {command.source} into {command.destination}')

    snapshot_meta = MetaWriter(command.destination, command.name)
    _initialize(command.destination)
    _process_backup(snapshot_meta, command.source, command.destination)


def update(command: commands.UpdateCommand) -> None:
    if not os.path.exists(command.source):
        raise ValueError(f'source path {command.source} does not exists')
    if not os.path.exists(command.destination):
        raise ValueError(
            f'destination path {command.destination} does not exists')
    if os.path.exists(os.path.join(command.destination, command.name + '.csv')):
        raise ValueError(
            f'There is already a backup versioned with the name {command.name}')

    print(
        f'Updating backup at {command.destination} with new version {command.name}')
    snapshot_meta = MetaWriter(command.destination, command.name)
    _process_backup(snapshot_meta, command.source, command.destination)


def check(command: commands.CheckCommand) -> List[str]:
    if not os.path.exists(command.destination):
        raise ValueError(
            f'destination path {command.destination} does not exists')
    if command.name is not None and not os.path.exists(os.path.join(command.destination, command.name + '.csv')):
        raise ValueError(
            f'Backup version named {command.name} does not exists at {command.destination}')

    metas = _metas_to_check(command)
    errors = []

    for meta in metas:
        errors += _check_missing_hashes(meta)

    for error in errors:
        print(error)
    if len(errors) == 0:
        print('No errors found!')

    return errors
