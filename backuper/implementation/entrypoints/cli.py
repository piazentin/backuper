import asyncio
import os
from pathlib import Path

from backuper.implementation import config as implementation_config
from backuper.implementation.commands import (
    CheckCommand,
    NewCommand,
    RestoreCommand,
    UpdateCommand,
)
from backuper.implementation.components.backup_analyzer import BackupAnalyzerImpl
from backuper.implementation.components.csv_db import (
    CsvBackupDatabase,
    CsvDb,
)
from backuper.implementation.components.file_reader import LocalFileReader
from backuper.implementation.components.filestore import LocalFileStore
from backuper.implementation.config import CsvDbConfig, FilestoreConfig
from backuper.implementation.controllers.backup import add_version, new_backup
from backuper.implementation.controllers.check import run_check_flow
from backuper.implementation.controllers.restore import run_restore_flow


def _csv_db(backup_root: Path) -> CsvDb:
    return CsvDb(CsvDbConfig(backup_dir=str(backup_root)))


def _local_filestore(backup_root: Path) -> LocalFileStore:
    return LocalFileStore(
        FilestoreConfig(
            backup_dir=str(backup_root),
            zip_enabled=implementation_config.ZIP_ENABLED,
        )
    )


def _present_check_stdout(errors: list[str]) -> None:
    for error in errors:
        print(error)
    if len(errors) == 0:
        print("No errors found!")


def run_new(command: NewCommand) -> None:
    source = Path(command.source)
    destination = Path(command.location)
    if not source.exists():
        raise ValueError(f"source path {command.source} does not exists")
    if destination.exists():
        raise ValueError(f"destination path {command.location} already exists")

    asyncio.run(
        new_backup(
            source,
            command.version,
            file_reader=LocalFileReader(),
            analyzer=BackupAnalyzerImpl(),
            db=CsvBackupDatabase(_csv_db(destination)),
            filestore=_local_filestore(destination),
        )
    )


def run_update(command: UpdateCommand) -> None:
    source = Path(command.source)
    destination = Path(command.location)
    if not source.exists():
        raise ValueError(f"source path {command.source} does not exists")
    if not destination.exists():
        raise ValueError(f"destination path {command.location} does not exists")

    asyncio.run(
        add_version(
            source,
            command.version,
            file_reader=LocalFileReader(),
            analyzer=BackupAnalyzerImpl(),
            db=CsvBackupDatabase(_csv_db(destination)),
            filestore=_local_filestore(destination),
        )
    )


def run_check(command: CheckCommand) -> list[str]:
    destination = Path(command.location)
    if not destination.exists():
        raise ValueError(f"destination path {command.location} does not exists")

    errors = asyncio.run(
        run_check_flow(
            command,
            db=CsvBackupDatabase(_csv_db(destination)),
            filestore=_local_filestore(destination),
        )
    )
    _present_check_stdout(errors)

    return errors


def run_restore(command: RestoreCommand) -> None:
    source = Path(command.location)
    destination = Path(command.destination)
    if not source.exists():
        raise ValueError(f"Backup source path {command.location} does not exists")
    if destination.exists() and any(os.scandir(destination)):
        raise ValueError(
            f'Backup restore destination "{command.destination}" '
            "already exists and is not empty"
        )

    asyncio.run(
        run_restore_flow(
            command,
            db=CsvBackupDatabase(_csv_db(source)),
            filestore=_local_filestore(source),
            on_restore_file=lambda relative_path: print(
                f"Restoring {relative_path} to {command.destination}"
            ),
        )
    )
