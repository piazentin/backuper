from pathlib import Path

from backuper.implementation.components.csv_db import CsvDb, Version
from backuper.implementation.components.filestore import LocalFileStore
from backuper.implementation.commands import CheckCommand
from backuper.implementation.config import CsvDbConfig, FilestoreConfig


def _missing_stored_files(
    version: Version, db: CsvDb, filestore: LocalFileStore
) -> list[str]:
    errors = []
    for file in db.get_files_for_version(version):
        if not filestore.exists(file.stored_location):
            errors.append(
                f"Missing hash {file.sha1hash} "
                f"for {file.restore_path} in {version.name}"
            )
    return errors


def run_check_flow(command: CheckCommand) -> list[str]:
    destination = Path(command.location)
    if not destination.exists():
        raise ValueError(f"destination path {command.location} does not exists")

    db = CsvDb(CsvDbConfig(backup_dir=str(destination)))
    filestore = LocalFileStore(FilestoreConfig(backup_dir=str(destination)))

    if command.version is None:
        versions = db.get_all_versions()
    else:
        try:
            versions = [db.get_version_by_name(command.version)]
        except RuntimeError as err:
            raise ValueError(
                f"Backup version named {command.version} "
                f"does not exists at {command.location}"
            ) from err

    errors: list[str] = []
    for version in versions:
        errors += _missing_stored_files(version, db, filestore)

    return errors
