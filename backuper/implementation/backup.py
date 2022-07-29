import os
import backuper.implementation.utils as utils
from typing import List

import backuper.implementation.commands as commands
import backuper.implementation.config as config
from backuper.implementation.csv_db import CsvDb
from backuper.implementation.filestore import Filestore
import backuper.implementation.models as models


def _process_dirs(
    version: models.Version, relative_path: str, dirs: List[str], db: CsvDb
) -> None:
    for dir in dirs:
        dirname = os.path.join(relative_path, dir)
        db.insert_dir(version, models.DirEntry(dirname))


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


def _process_files(
    version: models.Version,
    full_path: str,
    relative_path: str,
    filenames: List[str],
    db: CsvDb,
    filestore: Filestore,
) -> None:
    for filename in filenames:
        file_to_copy = os.path.join(full_path, filename)
        relative_filename = os.path.join(relative_path, filename)
        stored_file = filestore.put(file_to_copy, relative_filename)
        db.insert_file(version, stored_file)


def _process_backup(
    version: models.Version,
    source: str,
    db: CsvDb,
    filestore: Filestore,
) -> None:
    for dirpath, dirnames, filenames in os.walk(source, topdown=True):
        relative_path = utils.absolute_to_relative_path(source, dirpath)
        print(f'Processing "{relative_path}"...')
        _process_dirs(version, relative_path, dirnames, db)
        _process_files(version, dirpath, relative_path, filenames, db, filestore)


def _check_missing_hashes(
    version: models.Version, db: CsvDb, filestore: Filestore
) -> List[str]:
    errors = []
    for file in db.get_files_for_version(version):
        if not is_file_already_backuped(filestore._config.backup_dir, file.sha1hash):
            errors.append(
                f"Missing hash {file.sha1hash} "
                f"for {file.restore_path} in {version.name}"
            )
    return errors


def _restore_version(
    version: models.Version, destination: str, db: CsvDb, filestore: Filestore
) -> None:
    for entry in db.get_fs_objects_for_version(version):
        if isinstance(entry, models.DirEntry):
            absolute_path = utils.relative_to_absolute_path(destination, entry.name)
            create_dir_if_not_exists(absolute_path)
        elif isinstance(entry, models.StoredFile):
            print(f"Restoring {entry.restore_path} to {destination}")
            filestore.restore(entry, destination)


def new(command: commands.NewCommand) -> None:
    if not os.path.exists(command.source):
        raise ValueError(f"source path {command.source} does not exists")
    if os.path.exists(command.location):
        raise ValueError(f"destination path {command.location} already exists")

    db = CsvDb(config.CsvDbConfig(backup_dir=command.location))
    filestore = Filestore(
        config.FilestoreConfig(backup_dir=command.location, zip_enabled=command.zip)
    )
    version = models.Version(command.version)

    print(f"Creating new backup from {command.source} " f"into {command.location}")
    _process_backup(version, command.source, db, filestore)


def update(command: commands.UpdateCommand) -> None:
    db = CsvDb(config.CsvDbConfig(backup_dir=command.location))
    filestore = Filestore(
        config.FilestoreConfig(backup_dir=command.location, zip_enabled=command.zip)
    )
    version = models.Version(command.version)

    if not os.path.exists(command.source):
        raise ValueError(f"source path {command.source} does not exists")
    if not os.path.exists(command.location):
        raise ValueError(f"destination path {command.location} does not exists")
    if db.maybe_get_version_by_name(command.version):
        raise ValueError(
            f"There is already a backup versioned " f"with the name {command.version}"
        )

    print(
        f"Updating backup at {command.location} " f"with new version {command.version}"
    )
    _process_backup(version, command.source, db, filestore)


def check(command: commands.CheckCommand) -> List[str]:
    db = CsvDb(config.CsvDbConfig(backup_dir=command.location))
    filestore = Filestore(config.FilestoreConfig(backup_dir=command.location))

    if not os.path.exists(command.location):
        raise ValueError(f"destination path {command.location} does not exists")

    if command.version is None:
        versions = db.get_all_versions()
    else:
        try:
            versions = [db.get_version_by_name(command.version)]
        except:
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
