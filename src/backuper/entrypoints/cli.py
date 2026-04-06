import asyncio
import os
from pathlib import Path

from backuper import config as implementation_config
from backuper.commands import (
    CheckCommand,
    NewCommand,
    RestoreCommand,
    UpdateCommand,
)
from backuper.components.backup_analyzer import BackupAnalyzerImpl
from backuper.components.csv_db import (
    CsvBackupDatabase,
    CsvDb,
)
from backuper.components.file_reader import LocalFileReader
from backuper.components.filestore import LocalFileStore
from backuper.config import CsvDbConfig, FilestoreConfig
from backuper.controllers.backup import add_version, new_backup
from backuper.controllers.check import run_check_flow
from backuper.controllers.restore import run_restore_flow
from backuper.interfaces import BackupAnalysisSummary


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


def _print_backup_analysis_summary(summary: BackupAnalysisSummary) -> None:
    print("Running analysis... This may take a while.")
    title_str = f"+++++ BACKUP ANALYSIS RESULT FOR VERSION {summary.version_name} +++++"
    print(title_str)
    print(f"Number of directories: {summary.num_directories}")
    print(f"Number of files: {summary.num_files}")
    print(f"Total size of files: {summary.total_file_size}")
    print(f"Files to backup: {summary.files_to_backup}")
    print("+" * len(title_str))


def _print_backup_file_progress(file_index: int, total_files: int) -> None:
    if total_files == 0:
        return
    print(f"Processed {format((file_index / total_files), '.0%')} of files...")


def run_new(command: NewCommand) -> None:
    source = Path(command.source)
    destination = Path(command.location)
    if not source.exists():
        raise ValueError(f"source path {command.source} does not exist")
    if destination.exists():
        raise ValueError(f"destination path {command.location} already exists")

    print(f"Creating new backup from {command.source} into {command.location}")
    asyncio.run(
        new_backup(
            source,
            command.version,
            file_reader=LocalFileReader(),
            analyzer=BackupAnalyzerImpl(),
            db=CsvBackupDatabase(_csv_db(destination), index_status=print),
            filestore=_local_filestore(destination),
            on_analysis_summary=_print_backup_analysis_summary,
            on_file_progress=_print_backup_file_progress,
        )
    )


def run_update(command: UpdateCommand) -> None:
    source = Path(command.source)
    destination = Path(command.location)
    if not source.exists():
        raise ValueError(f"source path {command.source} does not exist")
    if not destination.exists():
        raise ValueError(f"destination path {command.location} does not exist")

    print(f"Updating backup at {command.location} with new version {command.version}")
    asyncio.run(
        add_version(
            source,
            command.version,
            file_reader=LocalFileReader(),
            analyzer=BackupAnalyzerImpl(),
            db=CsvBackupDatabase(_csv_db(destination), index_status=print),
            filestore=_local_filestore(destination),
            on_analysis_summary=_print_backup_analysis_summary,
            on_file_progress=_print_backup_file_progress,
        )
    )


def run_check(command: CheckCommand) -> list[str]:
    destination = Path(command.location)
    if not destination.exists():
        raise ValueError(f"destination path {command.location} does not exist")

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
        raise ValueError(f"Backup source path {command.location} does not exist")
    if destination.exists():
        with os.scandir(destination) as entries:
            if any(entries):
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
