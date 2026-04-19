from __future__ import annotations

import csv
import logging
import os
import uuid
from collections.abc import AsyncGenerator, Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Union, cast
from uuid import UUID

from backuper.config import CsvDbConfig
from backuper.models import (
    BackedUpFileEntry,
    FileEntry,
    MalformedBackupCsvError,
    VersionNotFoundError,
)
from backuper.ports import BackupDatabase
from backuper.utils.paths import normalize_path

_logger = logging.getLogger(__name__)

_StoredLocation = str


@dataclass(frozen=True)
class _DirEntry:
    name: str

    def normalized_path(self) -> str:
        return normalize_path(self.name)


@dataclass
class _Version:
    name: str


@dataclass(frozen=True)
class _StoredFile:
    restore_path: str
    sha1hash: str
    stored_location: _StoredLocation
    is_compressed: bool
    size: int = 0
    mtime: float = 0.0


_FileSystemObject = Union[_DirEntry, _StoredFile]


def _csvrow_to_model(row) -> _FileSystemObject:
    if not row:
        raise MalformedBackupCsvError("Empty CSV row")
    kind = row[0]
    if kind == "d":
        return _DirEntry(row[1])
    if kind == "f":
        if len(row) >= 7:
            _, restore_path, sha1hash, stored_location, is_compressed, size, mtime = (
                row[:7]
            )
            try:
                parsed_size = int(size) if size else 0
            except ValueError as e:
                raise MalformedBackupCsvError(
                    f"Invalid file CSV row: size field is not a valid integer: {size!r}"
                ) from e
            try:
                parsed_mtime = float(mtime) if mtime else 0.0
            except ValueError as e:
                raise MalformedBackupCsvError(
                    f"Invalid file CSV row: mtime field is not a valid float: {mtime!r}"
                ) from e
            return _StoredFile(
                restore_path,
                sha1hash,
                stored_location,
                is_compressed == "True",
                parsed_size,
                parsed_mtime,
            )
        raise MalformedBackupCsvError(
            f"Unsupported file CSV row: expected at least 7 columns "
            f"(only the first 7 fields are used when more are present), got {len(row)}"
        )
    raise MalformedBackupCsvError(f"Unknown CSV row type: {kind!r}")


def _iter_nonempty_version_csv_rows(file, *, version_name: str) -> Iterator[list[str]]:
    """Yield CSV rows; log a warning and skip rows that parse as empty."""
    for row in csv.reader(file, delimiter=",", quotechar='"'):
        if not row:
            _logger.warning(
                "Skipping empty row in version CSV (version name %r)",
                version_name,
            )
            continue
        yield row


def _model_to_csvrow(model: _FileSystemObject) -> str:
    if isinstance(model, _DirEntry):
        return f'"d","{model.normalized_path()}",""\n'
    elif isinstance(model, _StoredFile):
        return f'"f","{model.restore_path}","{model.sha1hash}","{model.stored_location}","{model.is_compressed}","{model.size}","{model.mtime}"\n'
    else:
        raise MalformedBackupCsvError("Do not know how to parse object")


class CsvDb:
    def __init__(self, config: CsvDbConfig) -> None:
        self._config = config
        self.db_dir = os.path.join(self._config.backup_dir, self._config.backup_db_dir)
        os.makedirs(self.db_dir, exist_ok=True)

    def _csv_path_from_name(self, name: str) -> str:
        return os.path.join(self.db_dir, name + self._config.csv_file_extension)

    def get_all_versions(self) -> list[_Version]:
        ext = self._config.csv_file_extension
        return [
            _Version(f.removesuffix(ext))
            for f in os.listdir(self.db_dir)
            # Skip dotfiles (e.g. macOS AppleDouble `._name.csv` sidecars are not UTF-8 CSV).
            if f.endswith(ext) and not f.startswith(".")
        ]

    def create_version(self, name: str) -> _Version:
        version_file = self._csv_path_from_name(name)
        with open(version_file, "a", encoding="utf-8"):
            pass
        return _Version(name)

    def maybe_get_version_by_name(self, name: str) -> _Version | None:
        if os.path.exists(self._csv_path_from_name(name)):
            return _Version(name)
        return None

    def get_most_recent_version(self) -> _Version | None:
        """Pick the version whose ``name`` is greatest by lexicographic (string) order.

        Each backup version is a CSV file named ``{name}{extension}`` under the DB
        directory; there is no separate timestamp column. "Most recent" is therefore
        defined as the **maximum** ``version.name`` in ordinary string sorting—not
        numeric order, not filesystem mtime. For example, ``\"v10\"`` sorts *before*
        ``\"v2\"``, so ``\"v2\"`` would be returned when both exist.

        Returns ``None`` when there are no version CSV files (dotfiles such as
        AppleDouble ``._*.csv`` sidecars are ignored by :meth:`get_all_versions`).
        """
        versions = sorted(
            self.get_all_versions(), key=lambda version: version.name, reverse=True
        )
        if len(versions) > 0:
            return versions[0]
        else:
            return None

    def get_version_by_name(self, name: str) -> _Version:
        if self.maybe_get_version_by_name(name):
            return _Version(name)
        else:
            raise VersionNotFoundError(name)

    def get_fs_objects_for_version(self, version: _Version) -> list[_FileSystemObject]:
        version_file = self._csv_path_from_name(version.name)
        with open(version_file, encoding="utf-8") as file:
            return [
                _csvrow_to_model(row)
                for row in _iter_nonempty_version_csv_rows(
                    file, version_name=version.name
                )
            ]

    def get_dirs_for_version(self, version: _Version) -> list[_DirEntry]:
        version_file = self._csv_path_from_name(version.name)
        with open(version_file, encoding="utf-8") as file:
            return [
                cast(_DirEntry, _csvrow_to_model(row))
                for row in _iter_nonempty_version_csv_rows(
                    file, version_name=version.name
                )
                if row and row[0] == "d"
            ]

    def get_files_for_version(self, version: _Version) -> list[_StoredFile]:
        version_file = self._csv_path_from_name(version.name)
        if not os.path.exists(version_file):
            return []

        with open(version_file, encoding="utf-8") as file:
            return [
                cast(_StoredFile, _csvrow_to_model(row))
                for row in _iter_nonempty_version_csv_rows(
                    file, version_name=version.name
                )
                if row and row[0] == "f"
            ]

    def insert_dir(self, version: _Version, dir: _DirEntry) -> None:
        version_file = self._csv_path_from_name(version.name)
        with open(version_file, "a", encoding="utf-8", newline="") as writer:
            writer.write(_model_to_csvrow(dir))

    def insert_file(self, version: _Version, file: _StoredFile) -> None:
        version_file = self._csv_path_from_name(version.name)
        with open(version_file, "a", encoding="utf-8", newline="") as writer:
            writer.write(_model_to_csvrow(file))


class CsvBackupDatabase(BackupDatabase):
    def __init__(
        self,
        csv_db: CsvDb,
        *,
        index_status: Callable[[str], None] | None = None,
    ) -> None:
        self._csv_db = csv_db
        self._index_status = index_status
        self._file_indexes_valid: bool = False
        self._files_by_restore_path: dict[str, list[_StoredFile]] = {}
        self._files_by_hash: dict[str, list[_StoredFile]] = {}
        if index_status is not None:
            self._ensure_file_indexes()

    def _ensure_file_indexes(self) -> None:
        if self._file_indexes_valid:
            return
        status = self._index_status
        if status is not None:
            status("Building index")
        by_path: dict[str, list[_StoredFile]] = {}
        by_hash: dict[str, list[_StoredFile]] = {}
        for version in self._csv_db.get_all_versions():
            for sf in self._csv_db.get_files_for_version(version):
                by_path.setdefault(sf.restore_path, []).append(sf)
                by_hash.setdefault(sf.sha1hash, []).append(sf)
        self._files_by_restore_path = by_path
        self._files_by_hash = by_hash
        self._file_indexes_valid = True
        if status is not None:
            status("Index built")

    def _stored_file_to_backup_entry(
        self, stored_file: _StoredFile
    ) -> BackedUpFileEntry:
        path = Path(stored_file.restore_path)
        source_file = FileEntry(
            path=path,
            relative_path=path,
            size=stored_file.size,
            mtime=stored_file.mtime,
            is_directory=False,
        )
        backup_id = self._generate_uuid_from_hash(stored_file.sha1hash)
        return BackedUpFileEntry(
            source_file=source_file,
            backup_id=backup_id,
            stored_location=stored_file.stored_location,
            is_compressed=stored_file.is_compressed,
            hash=stored_file.sha1hash,
        )

    async def list_versions(self) -> list[str]:
        names = [version.name for version in self._csv_db.get_all_versions()]
        return sorted(names)

    async def get_version_by_name(self, name: str) -> str:
        return self._csv_db.get_version_by_name(name).name

    async def list_files(self, version: str) -> AsyncGenerator[FileEntry, None]:
        version_obj = self._csv_db.get_version_by_name(version)
        stored_files: list[_StoredFile] = []
        dir_entries: list[_DirEntry] = []
        for obj in self._csv_db.get_fs_objects_for_version(version_obj):
            if isinstance(obj, _StoredFile):
                stored_files.append(obj)
            else:
                dir_entries.append(obj)

        for stored_file in stored_files:
            path = Path(stored_file.restore_path)

            yield FileEntry(
                path=path,
                relative_path=path,
                size=stored_file.size,
                mtime=stored_file.mtime,
                is_directory=False,
                hash=stored_file.sha1hash,
                stored_location=stored_file.stored_location,
                is_compressed=stored_file.is_compressed,
            )

        for dir_entry in dir_entries:
            path = Path(dir_entry.name)
            yield FileEntry(
                path=path, relative_path=path, size=0, mtime=0.0, is_directory=True
            )

    async def create_version(self, version: str) -> None:
        self._csv_db.create_version(version)

    async def add_file(self, version: str, entry: BackedUpFileEntry) -> None:
        version_obj = self._csv_db.get_version_by_name(version)

        if entry.source_file.is_directory:
            dir_entry = _DirEntry(str(entry.source_file.relative_path))
            self._csv_db.insert_dir(version_obj, dir_entry)
            return

        stored_file = _StoredFile(
            restore_path=str(entry.source_file.relative_path),
            sha1hash=entry.hash or "",
            stored_location=entry.stored_location,
            is_compressed=entry.is_compressed,
            size=entry.source_file.size,
            mtime=entry.source_file.mtime,
        )
        self._csv_db.insert_file(version_obj, stored_file)
        if self._file_indexes_valid:
            self._files_by_restore_path.setdefault(stored_file.restore_path, []).append(
                stored_file
            )
            self._files_by_hash.setdefault(stored_file.sha1hash, []).append(stored_file)

    async def get_files_by_hash(self, hash: str) -> list[BackedUpFileEntry]:
        """Get file entries by their hash value"""
        self._ensure_file_indexes()
        result = []
        for stored_file in self._files_by_hash.get(hash, []):
            result.append(self._stored_file_to_backup_entry(stored_file))
        return result

    async def get_files_by_metadata(
        self, relative_path: Path, mtime: float, size: int
    ) -> list[BackedUpFileEntry]:
        """Get file entries by their metadata (relative path, mtime, and size)"""
        self._ensure_file_indexes()
        rel = str(relative_path)
        result = []
        for stored_file in self._files_by_restore_path.get(rel, []):
            if abs(stored_file.mtime - mtime) < 0.001 and stored_file.size == size:
                result.append(self._stored_file_to_backup_entry(stored_file))

        return result

    def _generate_uuid_from_hash(self, hash: str) -> UUID:
        """Generate a deterministic UUID based on a hash value"""
        return uuid.uuid5(uuid.NAMESPACE_DNS, hash)
