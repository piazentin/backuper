import asyncio
from pathlib import Path

from backuper.implementation.components.backup_analyzer import BackupAnalyzerImpl
from backuper.implementation.components.csv_db import CsvBackupDatabase, CsvDb
from backuper.implementation.components.file_reader import LocalFileReader
from backuper.implementation.components.filestore import LocalFileStore
from backuper.implementation.config import CsvDbConfig, FilestoreConfig
from backuper.implementation.controllers.create_backup import CreateBackupController
from backuper.legacy.implementation.commands import NewCommand


def run_new(command: NewCommand) -> None:
    destination = Path(command.location)
    controller = CreateBackupController(
        file_reader=LocalFileReader(),
        analyzer=BackupAnalyzerImpl(),
        db=CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=str(destination)))),
        filestore=LocalFileStore(FilestoreConfig(backup_dir=str(destination))),
    )
    asyncio.run(controller.create_backup(Path(command.source), command.version))
