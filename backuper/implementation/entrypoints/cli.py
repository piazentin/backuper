import asyncio
from pathlib import Path

from backuper.implementation import config as implementation_config
from backuper.implementation.components.backup_analyzer import BackupAnalyzerImpl
from backuper.implementation.components.csv_db import (
    CsvBackupDatabase,
    CsvDb,
)
from backuper.implementation.components.file_reader import LocalFileReader
from backuper.implementation.components.filestore import LocalFileStore
from backuper.implementation.commands import CheckCommand, NewCommand, UpdateCommand
from backuper.implementation.config import CsvDbConfig, FilestoreConfig
from backuper.implementation.controllers.backup import add_version, new_backup
from backuper.implementation.controllers.check import run_check_flow


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
