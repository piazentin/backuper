from datetime import datetime
import os
from pathlib import Path
from backuper.implementation.analyze import Analyze
import backuper.implementation.utils as utils
from typing import List

import backuper.implementation.commands as commands
import backuper.implementation.config as config
from backuper.implementation.csv_db import CsvDb
from backuper.implementation.filestore import Filestore
import backuper.implementation.models as models


def _process_backup(
    version: models.Version,
    source: str,
    db: CsvDb,
    filestore: Filestore,
) -> None:
    print("Running analysis... This may take a while.")
    analyze = Analyze(source)
    title_str = f"+++++ BACKUP ANALYSIS RESULT FOR VERSION {version.name} +++++"
    print(title_str)
    print(f"Number of directories: {len(analyze.dirs)}")
    print(f"Number of files: {len(analyze.files)}")
    print(f"Total size of files: {sum(f.size for f in analyze.files)}")
    print("+" * len(title_str))

    for dir in analyze.dirs:
        db.insert_dir(version, models.DirEntry(dir.relative_path))

    for file in analyze.files:
        stored_file = filestore.put(file.absolute_path, file.relative_path, file.hash)
        db.insert_file(version, stored_file)


def _check_missing_stored_files(
    version: models.Version, db: CsvDb, filestore: Filestore
) -> List[str]:
    errors = []
    for file in db.get_files_for_version(version):
        if not filestore.exists(file.stored_location):
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
            os.makedirs(absolute_path, exist_ok=True)
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
        config.FilestoreConfig(
            backup_dir=command.location, zip_enabled=config.ZIP_ENABLED
        )
    )
    version = models.Version(command.version)

    print(f"Creating new backup from {command.source} " f"into {command.location}")
    _process_backup(version, command.source, db, filestore)


def update(command: commands.UpdateCommand) -> None:
    db = CsvDb(config.CsvDbConfig(backup_dir=command.location))
    filestore = Filestore(
        config.FilestoreConfig(
            backup_dir=command.location, zip_enabled=config.ZIP_ENABLED
        )
    )
    version = models.Version(command.version)

    if not os.path.exists(command.source):
        raise ValueError(f"source path {command.source} does not exists")
    if not os.path.exists(command.location):
        raise ValueError(f"destination path {command.location} does not exists")
    if db.maybe_get_version_by_name(command.version):
        raise ValueError(
            f"There is already a backup versioned with the name {command.version}"
        )

    print(f"Updating backup at {command.location} with new version {command.version}")
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
        errors += _check_missing_stored_files(version, db, filestore)

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
