import logging
from collections.abc import Callable
from pathlib import Path

from backuper.commands import RestoreCommand
from backuper.interfaces import BackupDatabase, FileStore, VersionNotFoundError

_logger = logging.getLogger(__name__)


def _resolved_path_under_destination(destination: Path, relative_path: Path) -> Path:
    if relative_path.is_absolute():
        raise ValueError(f"Invalid restore entry path (absolute): {relative_path}")
    root = destination.resolve()
    candidate = (destination / relative_path).resolve()
    if candidate != root and not candidate.is_relative_to(root):
        raise ValueError(
            f"Invalid restore entry path (outside destination): {relative_path}"
        )
    return candidate


async def run_restore_flow(
    command: RestoreCommand,
    *,
    db: BackupDatabase,
    filestore: FileStore,
    on_restore_file: Callable[[Path], None] | None = None,
) -> None:
    try:
        version_name = await db.get_version_by_name(command.version_name)
    except VersionNotFoundError as err:
        raise ValueError(
            f"Backup version {command.version_name} does not exist in source"
        ) from err

    destination = Path(command.destination)
    skipped_missing_hash = 0

    async for entry in db.list_files(version_name):
        restore_path = _resolved_path_under_destination(
            destination, entry.relative_path
        )
        if entry.is_directory:
            restore_path.mkdir(parents=True, exist_ok=True)
            continue

        file_hash = entry.hash
        if not file_hash:
            skipped_missing_hash += 1
            _logger.warning(
                "Skipping restore for %s: missing hash in version %s",
                entry.relative_path,
                version_name,
            )
            continue

        restore_path.parent.mkdir(parents=True, exist_ok=True)

        if on_restore_file is not None:
            on_restore_file(entry.relative_path)

        restore_path.write_bytes(
            filestore.read_blob(file_hash, is_compressed=entry.is_compressed)
        )

    if skipped_missing_hash:
        _logger.warning(
            "Skipped %d file(s) with missing hash during restore",
            skipped_missing_hash,
        )
