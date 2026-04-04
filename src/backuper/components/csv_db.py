from __future__ import annotations

import csv
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Union
from uuid import UUID

from backuper.components.utils import normalize_path
from backuper.config import CsvDbConfig
from backuper.interfaces import (
    BackupDatabase,
    BackupedFileEntry,
    FileEntry,
)

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
        raise ValueError("Empty CSV row")
    kind = row[0]
    if kind == "d":
        return _DirEntry(row[1])
    if kind == "f":
        if len(row) >= 7:
            _, restore_path, sha1hash, stored_location, is_compressed, size, mtime = row
            return _StoredFile(
                restore_path,
                sha1hash,
                stored_location,
                is_compressed == "True",
                int(size) if size else 0,
                float(mtime) if mtime else 0.0,
            )
        # Handle old format without size and mtime
        _, restore_path, sha1hash, stored_location, is_compressed = row
        return _StoredFile(
            restore_path, sha1hash, stored_location, is_compressed == "True"
        )
    raise ValueError(f"Unknown CSV row type: {kind!r}")


def _model_to_csvrow(model: _FileSystemObject) -> str:
    if isinstance(model, _DirEntry):
        return f'"d","{model.normalized_path()}",""\n'
    elif isinstance(model, _StoredFile):
        return f'"f","{model.restore_path}","{model.sha1hash}","{model.stored_location}","{model.is_compressed}","{model.size}","{model.mtime}"\n'
    else:
        raise ValueError("Do not know how to parse object")


class CsvDb:
    def __init__(self, config: CsvDbConfig) -> None:
        self._config = config
        self.db_dir = os.path.join(self._config.backup_dir, self._config.backup_db_dir)
        os.makedirs(self.db_dir, exist_ok=True)

    def _csv_path_from_name(self, name: str) -> os.PathLike:
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
            raise RuntimeError("Version not found")

    def get_fs_objects_for_version(self, version: _Version) -> list[_FileSystemObject]:
        version_file = self._csv_path_from_name(version.name)
        with open(version_file, encoding="utf-8") as file:
            return [
                _csvrow_to_model(row)
                for row in csv.reader(file, delimiter=",", quotechar='"')
            ]

    def get_dirs_for_version(self, version: _Version) -> list[_DirEntry]:
        version_file = self._csv_path_from_name(version.name)
        with open(version_file, encoding="utf-8") as file:
            return [
                _csvrow_to_model(row)
                for row in csv.reader(file, delimiter=",", quotechar='"')
                if row[0] == "d"
            ]

    def get_files_for_version(self, version: _Version) -> list[_StoredFile]:
        version_file = self._csv_path_from_name(version.name)
        if not os.path.exists(version_file):
            return []

        with open(version_file, encoding="utf-8") as file:
            return [
                _csvrow_to_model(row)
                for row in csv.reader(file, delimiter=",", quotechar='"')
                if row[0] == "f"
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
    def __init__(self, csv_db: CsvDb):
        self._csv_db = csv_db

    async def list_versions(self) -> list[str]:
        return [version.name for version in self._csv_db.get_all_versions()]

    async def get_version_by_name(self, name: str) -> str:
        return self._csv_db.get_version_by_name(name).name

    async def list_files(self, version: str) -> AsyncIterator[FileEntry]:
        version_obj = self._csv_db.get_version_by_name(version)
        stored_files = self._csv_db.get_files_for_version(version_obj)

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

        stored_dirs = self._csv_db.get_dirs_for_version(version_obj)
        for dir_entry in stored_dirs:
            path = Path(dir_entry.name)
            yield FileEntry(
                path=path, relative_path=path, size=0, mtime=0.0, is_directory=True
            )

    async def create_version(self, version: str) -> None:
        self._csv_db.create_version(version)

    async def add_file(self, version: str, entry: BackupedFileEntry) -> None:
        version_obj = self._csv_db.get_version_by_name(version)

        if entry.source_file.is_directory:
            dir_entry = _DirEntry(str(entry.source_file.relative_path))
            self._csv_db.insert_dir(version_obj, dir_entry)
        else:
            stored_file = _StoredFile(
                restore_path=str(entry.source_file.relative_path),
                sha1hash=entry.hash or "",
                stored_location=entry.stored_location,
                is_compressed=entry.is_compressed,
                size=entry.source_file.size,
                mtime=entry.source_file.mtime,
            )
            self._csv_db.insert_file(version_obj, stored_file)

    async def get_files_by_hash(self, hash: str) -> list[BackupedFileEntry]:
        """Get file entries by their hash value"""
        result = []
        # Get all versions
        versions = self._csv_db.get_all_versions()

        # Search through all versions for files with the matching hash
        for version in versions:
            stored_files = self._csv_db.get_files_for_version(version)
            for stored_file in stored_files:
                if stored_file.sha1hash == hash:
                    path = Path(stored_file.restore_path)
                    source_file = FileEntry(
                        path=path,
                        relative_path=path,
                        size=stored_file.size,
                        mtime=stored_file.mtime,
                        is_directory=False,
                    )

                    backup_id = self._generate_uuid_from_hash(stored_file.sha1hash)
                    result.append(
                        BackupedFileEntry(
                            source_file=source_file,
                            backup_id=backup_id,
                            stored_location=stored_file.stored_location,
                            is_compressed=stored_file.is_compressed,
                            hash=stored_file.sha1hash,
                        )
                    )

        return result

    async def get_files_by_metadata(
        self, relative_path: Path, mtime: float, size: int
    ) -> list[BackupedFileEntry]:
        """Get file entries by their metadata (relative path, mtime, and size)"""
        result = []
        # Get all versions
        versions = self._csv_db.get_all_versions()

        # Search through all versions for files with matching metadata
        for version in versions:
            stored_files = self._csv_db.get_files_for_version(version)
            for stored_file in stored_files:
                if (
                    stored_file.restore_path == str(relative_path)
                    and abs(stored_file.mtime - mtime)
                    < 0.001  # Use small epsilon for float comparison
                    and stored_file.size == size
                ):
                    path = Path(stored_file.restore_path)
                    source_file = FileEntry(
                        path=path,
                        relative_path=path,
                        size=stored_file.size,
                        mtime=stored_file.mtime,
                        is_directory=False,
                    )

                    backup_id = self._generate_uuid_from_hash(stored_file.sha1hash)
                    result.append(
                        BackupedFileEntry(
                            source_file=source_file,
                            backup_id=backup_id,
                            stored_location=stored_file.stored_location,
                            is_compressed=stored_file.is_compressed,
                            hash=stored_file.sha1hash,
                        )
                    )

        return result

    def _generate_uuid_from_hash(self, hash: str) -> UUID:
        """Generate a deterministic UUID based on a hash value"""
        return uuid.uuid5(uuid.NAMESPACE_DNS, hash)
