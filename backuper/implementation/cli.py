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
from backuper.implementation.controllers.backup import BackupController
from backuper.implementation.controllers.check import run_check_flow


def _backup_controller(backup_root: Path) -> BackupController:
    d = str(backup_root)
    return BackupController(
        file_reader=LocalFileReader(),
        analyzer=BackupAnalyzerImpl(),
        db=CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=d))),
        filestore=LocalFileStore(
            FilestoreConfig(
                backup_dir=d,
                zip_enabled=implementation_config.ZIP_ENABLED,
            )
        ),
    )


def run_new(command: NewCommand) -> None:
    source = Path(command.source)
    destination = Path(command.location)
    if not source.exists():
        raise ValueError(f"source path {command.source} does not exists")
    if destination.exists():
        raise ValueError(f"destination path {command.location} already exists")

    controller = _backup_controller(destination)
    asyncio.run(controller.new_backup(source, command.version))


def run_update(command: UpdateCommand) -> None:
    source = Path(command.source)
    destination = Path(command.location)
    if not source.exists():
        raise ValueError(f"source path {command.source} does not exists")
    if not destination.exists():
        raise ValueError(f"destination path {command.location} does not exists")

    controller = _backup_controller(destination)
    asyncio.run(controller.add_version(source, command.version))


def run_check(command: CheckCommand) -> list[str]:
    errors = run_check_flow(command)
    for error in errors:
        print(error)
    if len(errors) == 0:
        print("No errors found!")

    return errors
