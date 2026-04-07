from pathlib import Path

from backuper.commands import CheckCommand
from backuper.models import VersionNotFoundError
from backuper.ports import BackupDatabase, FileStore


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
        primary_ok = filestore.exists(loc)
        hash_ok = False
        h = file_entry.hash
        if not primary_ok and h:
            hash_ok = filestore.blob_exists(h, True) or filestore.blob_exists(h, False)
        blob_ok = primary_ok or hash_ok
        if not primary_ok and hash_ok:
            errors.append(
                f"Manifest metadata mismatch for {file_entry.relative_path} in "
                f"{version}: stored_location {loc!r} is missing or inconsistent, but "
                f"blob for hash {h} exists under raw or zipped layout (CSV may not "
                f"match on-disk compression or path)"
            )
        elif not blob_ok:
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
        except VersionNotFoundError as err:
            raise VersionNotFoundError(
                err.name, location=Path(command.location)
            ) from err

    errors: list[str] = []
    for version in versions:
        errors += await _missing_stored_files(version, db=db, filestore=filestore)

    return errors
