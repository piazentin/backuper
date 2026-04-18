import asyncio
import json
import os
from pathlib import Path

from backuper import config as implementation_config
from backuper.commands import (
    NewCommand,
    RestoreCommand,
    UpdateCommand,
    VerifyIntegrityCommand,
)
from backuper.components.backup_analyzer import BackupAnalyzerImpl
from backuper.components.file_reader import LocalFileReader
from backuper.components.filestore import LocalFileStore
from backuper.components.path_ignore import GitIgnorePathFilter
from backuper.components.reporter import StdoutAnalysisReporter
from backuper.config import FilestoreConfig
from backuper.controllers.backup import add_version, new_backup
from backuper.controllers.restore import run_restore_flow
from backuper.controllers.verify_integrity import run_verify_integrity_flow
from backuper.entrypoints.cli.user_ignore_patterns import build_user_ignore_patterns
from backuper.entrypoints.wiring import create_backup_database
from backuper.models import CliUsageError


def _local_filestore(backup_root: Path) -> LocalFileStore:
    return LocalFileStore(
        FilestoreConfig(
            backup_dir=str(backup_root),
            zip_enabled=implementation_config.ZIP_ENABLED,
        )
    )


def _present_verify_integrity_stdout(errors: list[str], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps({"errors": errors}))
        return
    for error in errors:
        print(error)
    if len(errors) == 0:
        print("No errors found!")


def run_new(command: NewCommand) -> None:
    source = Path(command.source)
    destination = Path(command.location)
    if not source.exists():
        raise CliUsageError(f"source path {command.source} does not exist")
    if destination.exists():
        raise CliUsageError(f"destination path {command.location} already exists")

    user_patterns = build_user_ignore_patterns(
        ignore_patterns=command.ignore_patterns,
        ignore_files=command.ignore_files,
    )
    print(f"Creating new backup from {command.source} into {command.location}")
    asyncio.run(
        new_backup(
            source,
            command.version,
            file_reader=LocalFileReader(
                path_filter=GitIgnorePathFilter(user_patterns=user_patterns)
            ),
            analyzer=BackupAnalyzerImpl(),
            db=create_backup_database(destination, index_status=print),
            filestore=_local_filestore(destination),
            reporter=StdoutAnalysisReporter(),
        )
    )


def run_update(command: UpdateCommand) -> None:
    source = Path(command.source)
    destination = Path(command.location)
    if not source.exists():
        raise CliUsageError(f"source path {command.source} does not exist")
    if not destination.exists():
        raise CliUsageError(f"destination path {command.location} does not exist")

    user_patterns = build_user_ignore_patterns(
        ignore_patterns=command.ignore_patterns,
        ignore_files=command.ignore_files,
    )
    print(f"Updating backup at {command.location} with new version {command.version}")
    asyncio.run(
        add_version(
            source,
            command.version,
            file_reader=LocalFileReader(
                path_filter=GitIgnorePathFilter(user_patterns=user_patterns)
            ),
            analyzer=BackupAnalyzerImpl(),
            db=create_backup_database(destination, index_status=print),
            filestore=_local_filestore(destination),
            reporter=StdoutAnalysisReporter(),
        )
    )


def run_verify_integrity(command: VerifyIntegrityCommand) -> list[str]:
    destination = Path(command.location)
    if not destination.exists():
        raise CliUsageError(f"destination path {command.location} does not exist")

    errors = asyncio.run(
        run_verify_integrity_flow(
            command,
            db=create_backup_database(destination),
            filestore=_local_filestore(destination),
        )
    )
    _present_verify_integrity_stdout(errors, json_output=command.json_output)

    return errors


def run_restore(command: RestoreCommand) -> None:
    source = Path(command.location)
    destination = Path(command.destination)
    if not source.exists():
        raise CliUsageError(f"Backup source path {command.location} does not exist")
    if destination.exists():
        with os.scandir(destination) as entries:
            if any(entries):
                raise CliUsageError(
                    f'Backup restore destination "{command.destination}" '
                    "already exists and is not empty"
                )

    asyncio.run(
        run_restore_flow(
            command,
            db=create_backup_database(source),
            filestore=_local_filestore(source),
            on_restore_file=lambda relative_path: print(
                f"Restoring {relative_path} to {command.destination}"
            ),
        )
    )
