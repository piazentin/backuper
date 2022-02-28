import csv
import hashlib
import os
import shutil
import pathlib
from abc import ABC
from dataclasses import dataclass
from typing import IO, Iterator, List, Union
from zipfile import ZipFile, ZIP_DEFLATED

import backuper.commands as commands

VERSION_FILE_EXT = '.csv'
ZIPFILE_EXT = '.zip'
HASHING_BUFFER_SIZE = 65536  # 64kb
ZIP_SKIP_EXTENSIONS = {
    '.mp3', '.ogg', '.wma', '.7z', '.arj', '.deb', '.pkg', '.rar', '.rpm',
    '.gz', '.zip', '.jar', '.jpg', '.jpeg', '.png', '.pptx', '.xlsx',
    '.docx', '.mp4', '.avi', '.mov', '.rm', '.mkv', '.wmv'
}
ZIP_MIN_FILESIZE_IN_BYTES = 1024  # 1KB


@dataclass
class DirEntry:
    name: str


@dataclass
class FileEntry:
    name: str
    hash: str


class _MetaFileHandler(ABC):
    destination: str
    version: str
    is_open: bool

    _filename: str
    _file: IO

    def __init__(self, destination: str, version: str) -> None:
        version = version[:-4] if version.endswith('.csv') else version

        self.destination = destination
        self.version = version
        self._filename = os.path.join(destination, version + '.csv')
        self.is_open = False

    def _open(self, open_mode):
        if not self.is_open:
            self._file = open(self._filename, open_mode, encoding="utf-8")
            self.is_open = True
        return self

    def __exit__(self, *_) -> None:
        if self.is_open:
            self._file.close()
            self.is_open = False


class MetaWriter(_MetaFileHandler):
    def __enter__(self) -> 'MetaWriter':
        return self._open('x')

    def add_dir(self, dirname: str) -> None:
        if not self.is_open:
            raise ValueError('Meta is not open for writing')
        normalized = normalize_path(dirname)
        self._file.write(f'"d","{normalized}",""\n')

    def add_file(self, filename: str, hash: str) -> None:
        if not self.is_open:
            raise ValueError('Meta is not open for writing')
        normalized = normalize_path(filename)
        self._file.write(f'"f","{normalized}","{hash}"\n')


class MetaReader(_MetaFileHandler):
    def __enter__(self) -> 'MetaReader':
        self._open('r')

    def entries(self) -> Iterator[Union[DirEntry, FileEntry]]:
        for row in csv.reader(self._file, delimiter=',', quotechar='"'):
            if row[0] == 'd':
                yield DirEntry(row[1])
            elif row[0] == 'f':
                yield FileEntry(row[1], row[2])

    def file_entries(self) -> Iterator[FileEntry]:
        for entry in self.entries():
            if isinstance(entry, FileEntry):
                yield entry

    def dir_entries(self) -> Iterator[DirEntry]:
        for entry in self.entries():
            if isinstance(entry, DirEntry):
                yield entry


def relative_to_absolute_path(root_path: str, relative: str) -> str:
    return os.path.join(root_path, relative)


def absolute_to_relative_path(root_path: str, absolute: str) -> str:
    return absolute[len(root_path):]


def _process_dirs(snapshot_meta: MetaWriter, relative_path: str,
                  dirs: List[str]) -> None:
    for dir in dirs:
        dirname = os.path.join(relative_path, dir)
        snapshot_meta.add_dir(dirname)


def sha1_hash(filename: str) -> str:
    sha1 = hashlib.sha1()
    with open(filename, 'rb') as f:
        while True:
            data = f.read(HASHING_BUFFER_SIZE)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()


def normalize_path(path: str) -> str:
    return '/'.join(path.replace('\\', '/').strip('/').split('/'))


def create_dir_if_not_exists(dir: str) -> None:
    if not os.path.exists(dir):
        os.makedirs(dir)


def backuped_dirname(backup_dir: str, filehash: str) -> str:
    return os.path.join(backup_dir, 'data',
                        filehash[0], filehash[1], filehash[2], filehash[3])


def backuped_filename(backup_main_dir: str, hash: str, zip: bool) -> str:
    filename = os.path.join(backuped_dirname(backup_main_dir, hash), hash)
    if zip:
        filename = filename + ZIPFILE_EXT
    return filename


def is_file_already_backuped(backup_main_dir: str, filehash: str) -> bool:
    return (
        os.path.exists(backuped_filename(backup_main_dir, filehash, False)) or
        os.path.exists(backuped_filename(backup_main_dir, filehash, True))
    )


def prepare_file_destination(backup_main_dir: str, filehash: str) -> None:
    dirname = backuped_dirname(backup_main_dir, filehash)
    create_dir_if_not_exists(dirname)


def should_zip_file(file_to_copy: str) -> bool:
    ext = pathlib.Path(file_to_copy).suffix
    size = os.path.getsize(file_to_copy)
    return ext not in ZIP_SKIP_EXTENSIONS and size > ZIP_MIN_FILESIZE_IN_BYTES


def copy_file_if_not_exists(file_to_copy: str, destination: str) -> None:
    if not os.path.isfile(destination):
        filedir = os.path.dirname(destination)
        create_dir_if_not_exists(filedir)
        shutil.copyfile(file_to_copy, destination)


def create_zipped_file(backup_main_dir: str,
                       file_to_copy: str,
                       filehash: str) -> None:
    if not is_file_already_backuped(backup_main_dir, filehash):
        prepare_file_destination(backup_main_dir, filehash)
        filename = backuped_filename(backup_main_dir, filehash, True)
        with ZipFile(filename, mode='x') as zipfile:
            zipfile.write(file_to_copy, filehash,
                          compress_type=ZIP_DEFLATED)


def process_file(meta_writer: MetaWriter,
                 backup_main_dir: str,
                 relative_filename: str,
                 file_to_copy: str,
                 zip: bool) -> str:
    filehash = sha1_hash(file_to_copy)
    if not is_file_already_backuped(backup_main_dir, filehash):
        should_zip = zip and should_zip_file(file_to_copy)
        if should_zip:
            create_zipped_file(backup_main_dir, file_to_copy, filehash)
        else:
            filename_at_destination = backuped_filename(backup_main_dir,
                                                        filehash, should_zip)
            copy_file_if_not_exists(file_to_copy, filename_at_destination)
    meta_writer.add_file(relative_filename, filehash)


def _process_files(meta_writer: MetaWriter, full_path: str, relative_path: str,
                   backup_main_dir: str, filenames: List[str],
                   zip: bool) -> None:
    for filename in filenames:
        relative_filename = os.path.join(relative_path, filename)
        file_to_copy = os.path.join(full_path, filename)
        process_file(meta_writer, backup_main_dir, relative_filename,
                     file_to_copy, zip)


def _initialize(path: str) -> None:
    os.makedirs(path)
    os.mkdir(os.path.join(path, 'data'))


def _process_backup(meta_writer: MetaWriter, source: str,
                    destination: str, zip: bool) -> None:
    with meta_writer:
        for dirpath, dirnames, filenames in os.walk(source, topdown=True):
            relative_path = absolute_to_relative_path(source, dirpath)
            print(f'Processing "{relative_path}"...')
            _process_dirs(meta_writer, relative_path, dirnames)
            _process_files(meta_writer, dirpath, relative_path,
                           destination, filenames, zip)


def _metas_to_check(command: commands.CheckCommand) -> List[MetaReader]:
    if command.version:
        return [MetaReader(command.location, command.version)]
    else:
        return [MetaReader(command.location, n)
                for n in os.listdir(command.location) if n.endswith('.csv')]


def _check_missing_hashes(meta: MetaReader) -> List[str]:
    errors = []
    with meta:
        for entry in meta.file_entries():
            if not is_file_already_backuped(meta.destination, entry.hash):
                errors.append(f'Missing hash {entry.hash} '
                              f'for {entry.name} in {meta.version}')
    return errors


def _restore_dir(entry: DirEntry, destination: str) -> None:
    absolute_path = relative_to_absolute_path(destination,
                                              entry.name)
    create_dir_if_not_exists(absolute_path)


def _restore_file(backup_path: str, file_entry: FileEntry,
                  destination_dir: str) -> None:
    absolute_origin_filename = backuped_filename(backup_path, file_entry.hash,
                                                 False)
    absolute_dest_filename = relative_to_absolute_path(destination_dir,
                                                       file_entry.name)
    print(f'Restoring {absolute_origin_filename} to {absolute_dest_filename}')
    copy_file_if_not_exists(absolute_origin_filename, absolute_dest_filename)


def _restore_version(backup_path: str, version: str, destination: str) -> None:
    reader = MetaReader(backup_path, version)
    with reader:
        for entry in reader.entries():
            if isinstance(entry, DirEntry):
                _restore_dir(entry, destination)
            elif isinstance(entry, FileEntry):
                _restore_file(backup_path, entry, destination)


def _versions(backup_path: str) -> List[str]:
    return [f.strip(VERSION_FILE_EXT)
            for f in os.listdir(backup_path)
            if f.endswith(VERSION_FILE_EXT)]


def _version_exists(backup_path: str, version: str):
    return (backup_path is not None and
            version is not None and
            os.path.exists(os.path.join(backup_path, version + '.csv')))


def new(command: commands.NewCommand) -> None:
    if not os.path.exists(command.source):
        raise ValueError(f'source path {command.source} does not exists')
    if os.path.exists(command.location):
        raise ValueError(
            f'destination path {command.location} already exists')

    print(f'Creating new backup from {command.source} '
          f'into {command.location}')

    snapshot_meta = MetaWriter(command.location, command.version)
    _initialize(command.location)
    _process_backup(snapshot_meta, command.source,
                    command.location, command.zip)


def update(command: commands.UpdateCommand) -> None:
    if not os.path.exists(command.source):
        raise ValueError(f'source path {command.source} does not exists')
    if not os.path.exists(command.location):
        raise ValueError(
            f'destination path {command.location} does not exists')
    if _version_exists(command.location, command.version):
        raise ValueError(f'There is already a backup versioned '
                         f'with the name {command.version}')

    print(f'Updating backup at {command.location} '
          f'with new version {command.version}')
    snapshot_meta = MetaWriter(command.location, command.version)
    _process_backup(snapshot_meta, command.source, command.location,
                    command.zip)


def check(command: commands.CheckCommand) -> List[str]:
    if not os.path.exists(command.location):
        raise ValueError(
            f'destination path {command.location} does not exists')
    if (command.version is not None and
            not _version_exists(command.location, command.version)):
        raise ValueError(f'Backup version named {command.version} '
                         f'does not exists at {command.location}')

    metas = _metas_to_check(command)
    errors = []

    for meta in metas:
        errors += _check_missing_hashes(meta)

    for error in errors:
        print(error)
    if len(errors) == 0:
        print('No errors found!')

    return errors


def restore(command: commands.RestoreCommand) -> None:
    if not os.path.exists(command.location):
        raise ValueError(
            f'Backup source path {command.location} does not exists')
    if (os.path.exists(command.destination) and
            any(os.scandir(command.destination))):
        raise ValueError(
            f'Backup restore destination "{command.destination}" '
            'already exists and is not empty')
    if command.version_name not in _versions(command.location):
        raise ValueError(
            f'Backup version {command.version_name} does not exists in source')

    _restore_version(command.location, command.version_name,
                     command.destination)
