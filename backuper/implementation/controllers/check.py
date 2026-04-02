from backuper.implementation.commands import CheckCommand
from backuper.implementation.components.interfaces import BackupDatabase, FileStore


async def _missing_stored_files(
    version: str,
    *,
    db: BackupDatabase,
    filestore: FileStore,
) -> list[str]:
    errors: list[str] = []
    async for file_entry in db.list_files(version):
        if file_entry.is_directory:
            continue
        loc = file_entry.stored_location
        if not loc:
            continue
        if not filestore.exists(loc):
            errors.append(
                f"Missing hash {file_entry.hash} "
                f"for {file_entry.relative_path} in {version}"
            )
    return errors


async def run_check_flow(
    command: CheckCommand,
    *,
    db: BackupDatabase,
    filestore: FileStore,
) -> list[str]:
    if command.version is None:
        versions = await db.list_versions()
    else:
        try:
            versions = [await db.get_version_by_name(command.version)]
        except RuntimeError as err:
            raise ValueError(
                f"Backup version named {command.version} "
                f"does not exists at {command.location}"
            ) from err

    errors: list[str] = []
    for version in versions:
        errors += await _missing_stored_files(version, db=db, filestore=filestore)

    return errors
