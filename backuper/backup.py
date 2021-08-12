import hashlib
import os
import shutil
import csv

import backuper.commands as commands


class MetaFile:
    def __init__(self, destination, name, mode) -> None:
        if mode not in ['x', 'r']:
            raise ValueError('supported modes are x and r')
        self.destination = destination
        self.name = name
        self.filename = os.path.join(destination, name + '.csv')
        self.mode = mode
        self.is_open = False

    def __enter__(self):
        if not self.is_open:
            self.file = open(self.filename, self.mode)
            self.is_open = True
        return self

    def __exit__(self, *args):
        if self.is_open:
            self.file.close()
            self.is_open = False

    def add_dir(self, dirname):
        self.file.write(f'"d","{dirname}",""\n')

    def add_file(self, filename, hash):
        self.file.write(f'"f","{filename}","{hash}"\n')


def _to_relative_path(root: str, path: str) -> str:
    return path[len(root):]


def _process_dirs(snapshot_meta: MetaFile, relative_path: str, dirs):
    for dir in dirs:
        dirname = os.path.join(relative_path, dir)
        snapshot_meta.add_dir(dirname)


def sha1_hash(file_name):
    BUF_SIZE = 65536  # 64kb
    sha1 = hashlib.sha1()
    with open(file_name, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()


def _process_files(snapshot_meta: MetaFile, full_path, relative_path, destination_dirname, filenames):
    for filename in filenames:
        relative_filename = os.path.join(relative_path, filename)
        full_filename = os.path.join(full_path, filename)

        hash = sha1_hash(full_filename)
        destination_filename = os.path.join(destination_dirname, 'data', hash)
        if not os.path.isfile(destination_filename):
            shutil.copyfile(full_filename, destination_filename)
        snapshot_meta.add_file(relative_filename, hash)


def _initialize(path):
    os.makedirs(path)
    os.mkdir(os.path.join(path, 'data'))


def new(command: commands.NewCommand):
    if not os.path.exists(command.source):
        raise ValueError(f'source path {command.source} does not exists')
    if os.path.exists(command.destination):
        raise ValueError(
            f'destination path {command.destination} already exists')

    print(
        f'Creating new backup from {command.source} into {command.destination}')

    _initialize(command.destination)
    snapshot_meta = MetaFile(command.destination, command.name, 'x')
    with snapshot_meta:
        for dirpath, dirnames, filenames in os.walk(command.source, topdown=True):
            relative_path = _to_relative_path(command.source, dirpath)
            print(f'Processing "{relative_path}"...')
            _process_dirs(snapshot_meta, relative_path, dirnames)
            _process_files(snapshot_meta, dirpath, relative_path,
                           command.destination, filenames)


def update(command: commands.UpdateCommand):
    pass


def check_backup(destination):
    with open(os.path.join(destination, '0000-00-00T000000.csv'), 'r') as csvfile:
        data = csv.reader(csvfile, delimiter=',', quotechar='"')
        failed = False
        for row in data:
            if row[0] == 'f':
                backuped_file = os.path.join(destination, 'data', row[2])
                if not os.path.exists(backuped_file):
                    failed = True
                    print(f'ERROR: hash {row[2]} does not exists')
        if failed:
            print('Backup check detected errors')
        else:
            print('Backup check completed without errors')
