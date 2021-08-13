import hashlib
import os
import shutil
import csv

from typing import List

import backuper.commands as commands


class MetaFile:
    destination: str
    name: str
    mode: str
    is_open: bool

    _filename: str

    def __init__(self, destination: str, name: str, mode: str) -> None:
        if mode not in ['x', 'r']:
            raise ValueError(
                'supported modes are x (create and write) and r (read)')
        self.destination = destination
        self.name = name
        self._filename = os.path.join(destination, name + '.csv')
        self.mode = mode
        self.is_open = False

    def __enter__(self) -> 'MetaFile':
        if not self.is_open:
            self.file = open(self._filename, self.mode)
            self.is_open = True
        return self

    def __exit__(self, *_) -> None:
        if self.is_open:
            self.file.close()
            self.is_open = False

    def add_dir(self, dirname: str) -> None:
        if not (self.is_open and self.mode == 'x'):
            raise ValueError('Meta file is not open for writing')
        self.file.write(f'"d","{dirname}",""\n')

    def add_file(self, filename: str, hash: str) -> None:
        if not (self.is_open and self.mode == 'x'):
            raise ValueError('Meta file is not open for writing')
        self.file.write(f'"f","{filename}","{hash}"\n')


def _to_relative_path(root: str, path: str) -> str:
    return path[len(root):]


def _process_dirs(snapshot_meta: MetaFile, relative_path: str, dirs: List[str]) -> None:
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


def _process_files(snapshot_meta: MetaFile, full_path: str, relative_path: str, destination_dirname: str, filenames: List[str]) -> None:
    for filename in filenames:
        relative_filename = os.path.join(relative_path, filename)
        full_filename = os.path.join(full_path, filename)

        hash = sha1_hash(full_filename)
        destination_filename = os.path.join(destination_dirname, 'data', hash)
        if not os.path.isfile(destination_filename):
            shutil.copyfile(full_filename, destination_filename)
        snapshot_meta.add_file(relative_filename, hash)


def _initialize(path: str) -> None:
    os.makedirs(path)
    os.mkdir(os.path.join(path, 'data'))


def _process_backup(snapshot_meta: MetaFile, source: str, destination: str) -> None:
    with snapshot_meta:
        for dirpath, dirnames, filenames in os.walk(source, topdown=True):
            relative_path = _to_relative_path(source, dirpath)
            print(f'Processing "{relative_path}"...')
            _process_dirs(snapshot_meta, relative_path, dirnames)
            _process_files(snapshot_meta, dirpath,
                           relative_path, destination, filenames)


def new(command: commands.NewCommand) -> None:
    if not os.path.exists(command.source):
        raise ValueError(f'source path {command.source} does not exists')
    if os.path.exists(command.destination):
        raise ValueError(
            f'destination path {command.destination} already exists')

    print(
        f'Creating new backup from {command.source} into {command.destination}')

    snapshot_meta = MetaFile(command.destination, command.name, 'x')
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
    snapshot_meta = MetaFile(command.destination, command.name, 'x')
    _process_backup(snapshot_meta, command.source, command.destination)


def check_backup(command: commands.CheckCommand) -> List[str]:
    with open(os.path.join(command.destination, command.name + '.csv'), 'r') as csvfile:
        data = csv.reader(csvfile, delimiter=',', quotechar='"')
        failed = False
        for row in data:
            if row[0] == 'f':
                backuped_file = os.path.join(command.name, 'data', row[2])
                if not os.path.exists(backuped_file):
                    failed = True
                    print(f'ERROR: hash {row[2]} does not exists')
        if failed:
            print('Backup check detected errors')
        else:
            print('Backup check completed without errors')
