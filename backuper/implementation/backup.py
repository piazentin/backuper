import hashlib
import os
import shutil
import pathlib
from abc import ABC
from typing import IO, List
from zipfile import ZipFile, ZIP_DEFLATED

import backuper.implementation.commands as commands
import backuper.implementation.config as config
from backuper.implementation.csv_db import CsvDb
from backuper.implementation.filestore import Filestore
import backuper.implementation.models as models


class _MetaFileHandler(ABC):
    destination: str
    version: str
    is_open: bool

    _filename: str
    _file: IO

    def __init__(self, destination: str, version: str) -> None:
        version = version[:-4] if version.endswith(".csv") else version

        self.destination = destination
        self.version = version
        self._filename = os.path.join(destination, version + ".csv")
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
    def __enter__(self) -> "MetaWriter":
        return self._open("x")

    def add_dir(self, dirname: str) -> None:
        if not self.is_open:
            raise ValueError("Meta is not open for writing")
        normalized = normalize_path(dirname)
        self._file.write(f'"d","{normalized}",""\n')

    def add_file(self, filename: str, hash: str) -> None:
        if not self.is_open:
            raise ValueError("Meta is not open for writing")
        normalized = normalize_path(filename)
        self._file.write(f'"f","{normalized}","{hash}"\n')


def relative_to_absolute_path(root_path: str, relative: str) -> str:
    return os.path.join(root_path, relative)


def absolute_to_relative_path(root_path: str, absolute: str) -> str:
    return absolute[len(root_path) :]


def _process_dirs(
    snapshot_meta: MetaWriter, relative_path: str, dirs: List[str]
) -> None:
    for dir in dirs:
        dirname = os.path.join(relative_path, dir)
        snapshot_meta.add_dir(dirname)


def sha1_hash(filename: str) -> str:
    sha1 = hashlib.sha1()
    with open(filename, "rb") as f:
        while True:
            data = f.read(config.HASHING_BUFFER_SIZE)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()


def normalize_path(path: str) -> str:
    return "/".join(path.replace("\\", "/").strip("/").split("/"))


def create_dir_if_not_exists(dir: str) -> None:
    if not os.path.exists(dir):
        os.makedirs(dir)


def backuped_dirname(backup_dir: str, filehash: str) -> str:
    return os.path.join(
        backup_dir, "data", filehash[0], filehash[1], filehash[2], filehash[3]
    )


def backuped_filename(backup_main_dir: str, hash: str, zip: bool) -> str:
    filename = os.path.join(backuped_dirname(backup_main_dir, hash), hash)
    if zip:
        filename = filename + config.ZIPFILE_EXT
    return filename


def is_file_already_backuped(backup_main_dir: str, filehash: str) -> bool:
    return os.path.exists(
        backuped_filename(backup_main_dir, filehash, False)
    ) or os.path.exists(backuped_filename(backup_main_dir, filehash, True))


def prepare_file_destination(backup_main_dir: str, filehash: str) -> None:
    dirname = backuped_dirname(backup_main_dir, filehash)
    create_dir_if_not_exists(dirname)


def should_zip_file(file_to_copy: str) -> bool:
    ext = pathlib.Path(file_to_copy).suffix
    size = os.path.getsize(file_to_copy)
    return (
        ext not in config.ZIP_SKIP_EXTENSIONS
        and size > config.ZIP_MIN_FILESIZE_IN_BYTES
    )


def copy_file_if_not_exists(file_to_copy: str, destination: str) -> None:
    if not os.path.isfile(destination):
        filedir = os.path.dirname(destination)
        create_dir_if_not_exists(filedir)
        shutil.copyfile(file_to_copy, destination)


def create_zipped_file(backup_main_dir: str, file_to_copy: str, filehash: str) -> None:
    if not is_file_already_backuped(backup_main_dir, filehash):
        prepare_file_destination(backup_main_dir, filehash)
        filename = backuped_filename(backup_main_dir, filehash, True)
        with ZipFile(filename, mode="x") as zipfile:
            zipfile.write(file_to_copy, filehash, compress_type=ZIP_DEFLATED)


def process_file(
    meta_writer: MetaWriter,
    backup_main_dir: str,
    relative_filename: str,
    file_to_copy: str,
    zip: bool,
) -> str:
    filehash = sha1_hash(file_to_copy)
    if not is_file_already_backuped(backup_main_dir, filehash):
        should_zip = zip and should_zip_file(file_to_copy)
        if should_zip:
            create_zipped_file(backup_main_dir, file_to_copy, filehash)
        else:
            filename_at_destination = backuped_filename(
                backup_main_dir, filehash, should_zip
            )
            copy_file_if_not_exists(file_to_copy, filename_at_destination)
    meta_writer.add_file(relative_filename, filehash)


def _process_files(
    meta_writer: MetaWriter,
    full_path: str,
    relative_path: str,
    backup_main_dir: str,
    filenames: List[str],
    zip: bool,
) -> None:
    for filename in filenames:
        relative_filename = os.path.join(relative_path, filename)
        file_to_copy = os.path.join(full_path, filename)
        process_file(meta_writer, backup_main_dir, relative_filename, file_to_copy, zip)


def _initialize(path: str) -> None:
    os.makedirs(path)
    os.mkdir(os.path.join(path, "data"))


def _process_backup(
    meta_writer: MetaWriter, source: str, destination: str, zip: bool
) -> None:
    with meta_writer:
        for dirpath, dirnames, filenames in os.walk(source, topdown=True):
            relative_path = absolute_to_relative_path(source, dirpath)
            print(f'Processing "{relative_path}"...')
            _process_dirs(meta_writer, relative_path, dirnames)
            _process_files(
                meta_writer, dirpath, relative_path, destination, filenames, zip
            )


def _check_missing_hashes(
    version: models.Version, db: CsvDb, filestore: Filestore
) -> List[str]:
    errors = []
    for file in db.get_files_for_version(version):
        if not is_file_already_backuped(filestore._config.backup_dir, file.hash):
            errors.append(
                f"Missing hash {file.hash} " f"for {file.name} in {version.name}"
            )
    return errors


def _restore_dir(entry: models.DirEntry, destination: str) -> None:
    absolute_path = relative_to_absolute_path(destination, entry.name)
    create_dir_if_not_exists(absolute_path)


def _restore_file(
    backup_path: str, file_entry: models.FileEntry, destination_dir: str
) -> None:
    absolute_origin_filename = backuped_filename(backup_path, file_entry.hash, False)
    absolute_dest_filename = relative_to_absolute_path(destination_dir, file_entry.name)
    print(f"Restoring {absolute_origin_filename} to {absolute_dest_filename}")
    copy_file_if_not_exists(absolute_origin_filename, absolute_dest_filename)


def _restore_version(
    version: models.Version, destination: str, db: CsvDb, filestore: Filestore
) -> None:
    for entry in db.get_fs_objects_for_version(version):
        if isinstance(entry, models.DirEntry):
            _restore_dir(entry, destination)
        elif isinstance(entry, models.FileEntry):
            _restore_file(filestore._config.backup_dir, entry, destination)


def _version_exists(backup_path: str, version: str):
    return (
        backup_path is not None
        and version is not None
        and os.path.exists(os.path.join(backup_path, version + ".csv"))
    )


def new(command: commands.NewCommand) -> None:
    if not os.path.exists(command.source):
        raise ValueError(f"source path {command.source} does not exists")
    if os.path.exists(command.location):
        raise ValueError(f"destination path {command.location} already exists")

    print(f"Creating new backup from {command.source} " f"into {command.location}")

    snapshot_meta = MetaWriter(command.location, command.version)
    _initialize(command.location)
    _process_backup(snapshot_meta, command.source, command.location, command.zip)


def update(command: commands.UpdateCommand) -> None:
    if not os.path.exists(command.source):
        raise ValueError(f"source path {command.source} does not exists")
    if not os.path.exists(command.location):
        raise ValueError(f"destination path {command.location} does not exists")
    if _version_exists(command.location, command.version):
        raise ValueError(
            f"There is already a backup versioned " f"with the name {command.version}"
        )

    print(
        f"Updating backup at {command.location} " f"with new version {command.version}"
    )
    snapshot_meta = MetaWriter(command.location, command.version)
    _process_backup(snapshot_meta, command.source, command.location, command.zip)


def check(command: commands.CheckCommand) -> List[str]:
    db = CsvDb(config.CsvDbConfig(backup_dir=command.location))
    filestore = Filestore(config.FilestoreConfig(backup_dir=command.location))

    if not os.path.exists(command.location):
        raise ValueError(f"destination path {command.location} does not exists")

    if command.version is None:
        versions = db.get_all_versions()
    elif _version_exists(command.location, command.version):
        versions = [models.Version(command.version)]
    else:
        raise ValueError(
            f"Backup version named {command.version} "
            f"does not exists at {command.location}"
        )

    errors = []

    for version in versions:
        errors += _check_missing_hashes(version, db, filestore)

    for error in errors:
        print(error)
    if len(errors) == 0:
        print("No errors found!")

    return errors


def restore(command: commands.RestoreCommand) -> None:
    db = CsvDb(config.CsvDbConfig(backup_dir=command.location))
    filestore = Filestore(config.FilestoreConfig(backup_dir=command.location))
    version = models.Version(command.version_name)

    if not os.path.exists(command.location):
        raise ValueError(f"Backup source path {command.location} does not exists")
    if os.path.exists(command.destination) and any(os.scandir(command.destination)):
        raise ValueError(
            f'Backup restore destination "{command.destination}" '
            "already exists and is not empty"
        )
    if version not in db.get_all_versions():
        raise ValueError(
            f"Backup version {command.version_name} does not exists in source"
        )

    _restore_version(version, command.destination, db, filestore)
