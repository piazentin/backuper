from __future__ import annotations

import csv
import os
from operator import attrgetter

import backuper.legacy.implementation.models as models
from backuper.legacy.implementation.config import CsvDbConfig


def csvrow_to_model(row) -> models.FileSystemObject:
    if row[0] == "d":
        return models.DirEntry(row[1])
    elif row[0] == "f":
        if len(row) >= 7:
            _, restore_path, sha1hash, stored_location, is_compressed, size, mtime = row
            return models.StoredFile(
                restore_path,
                sha1hash,
                stored_location,
                is_compressed == "True",
                int(size) if size else 0,
                float(mtime) if mtime else 0.0,
            )
        else:
            # Handle old format without size and mtime
            _, restore_path, sha1hash, stored_location, is_compressed = row
            return models.StoredFile(
                restore_path, sha1hash, stored_location, is_compressed == "True"
            )


def model_to_csvrow(model: models.FileSystemObject) -> str:
    if isinstance(model, models.DirEntry):
        return f'"d","{model.normalized_path()}",""\n'
    elif isinstance(model, models.StoredFile):
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

    def get_all_versions(self) -> list[models.Version]:
        return [
            models.Version(f.strip(self._config.csv_file_extension))
            for f in os.listdir(self.db_dir)
            if f.endswith(self._config.csv_file_extension)
        ]

    def maybe_get_version_by_name(self, name: str) -> models.Version | None:
        if os.path.exists(self._csv_path_from_name(name)):
            return models.Version(name)
        return None

    def get_most_recent_version(self) -> models.Version | None:
        versions = sorted(self.get_all_versions(), key=attrgetter("name"), reverse=True)
        if len(versions) > 0:
            return versions[0]
        else:
            return None

    def get_version_by_name(self, name: str) -> models.Version:
        if self.maybe_get_version_by_name(name):
            return models.Version(name)
        else:
            raise RuntimeError("Version not found")

    def get_fs_objects_for_version(
        self, version: models.Version
    ) -> list[models.FileSystemObject]:
        version_file = self._csv_path_from_name(version.name)
        with open(version_file, encoding="utf-8") as file:
            return [
                csvrow_to_model(row)
                for row in csv.reader(file, delimiter=",", quotechar='"')
            ]

    def get_dirs_for_version(self, version: models.Version) -> list[models.DirEntry]:
        version_file = self._csv_path_from_name(version.name)
        with open(version_file, encoding="utf-8") as file:
            return [
                csvrow_to_model(row)
                for row in csv.reader(file, delimiter=",", quotechar='"')
                if row[0] == "d"
            ]

    def get_files_for_version(self, version: models.Version) -> list[models.StoredFile]:
        version_file = self._csv_path_from_name(version.name)
        if not os.path.exists(version_file):
            return []

        with open(version_file, encoding="utf-8") as file:
            return [
                csvrow_to_model(row)
                for row in csv.reader(file, delimiter=",", quotechar='"')
                if row[0] == "f"
            ]

    def insert_dir(self, version: models.Version, dir: models.DirEntry) -> None:
        version_file = self._csv_path_from_name(version.name)
        with open(version_file, "a") as writer:
            writer.write(model_to_csvrow(dir))

    def insert_file(self, version: models.Version, file: models.StoredFile) -> None:
        version_file = self._csv_path_from_name(version.name)
        with open(version_file, "a") as writer:
            writer.write(model_to_csvrow(file))
