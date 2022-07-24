import csv
import os
from typing import List
from backuper.implementation.config import CsvDbConfig
import backuper.implementation.models as models


def _fileobject_db_to_model(row) -> models.FileSystemObject:
    if row[0] == "d":
        return models.DirEntry(row[1])
    elif row[0] == "f":
        return models.FileEntry(row[1], row[2])


class CsvDb:
    def __init__(self, config: CsvDbConfig) -> None:
        self._config = config

    def _csv_path_from_version(self, version: models.Version) -> str:
        return os.path.join(self._config.backup_dir, version.name + ".csv")

    def get_all_versions(self) -> List[models.Version]:
        return [
            models.Version(f.strip(self._config.csv_file_extension))
            for f in os.listdir(self._config.backup_dir)
            if f.endswith(self._config.csv_file_extension)
        ]

    def get_fs_objects_for_version(
        self, version: models.Version
    ) -> List[models.FileSystemObject]:
        version_file = self._csv_path_from_version(version)
        with open(version_file, "r", encoding="utf-8") as file:
            return [
                _fileobject_db_to_model(row)
                for row in csv.reader(file, delimiter=",", quotechar='"')
            ]

    def get_files_for_version(self, version: models.Version) -> List[models.FileEntry]:
        version_file = self._csv_path_from_version(version)
        with open(version_file, "r", encoding="utf-8") as file:
            return [
                _fileobject_db_to_model(row)
                for row in csv.reader(file, delimiter=",", quotechar='"')
                if row[0] == "f"
            ]

    def insert_dir(self, version: models.Version, dir: models.DirEntry) -> None:
        version_file = self._csv_path_from_version(version)
        with open(version_file, "a") as writer:
            writer.write(f'"d","{dir.normalized_path()}",""\n')

    def insert_file(self, version: models.Version, file: models.FileEntry) -> None:
        version_file = self._csv_path_from_version(version)
        with open(version_file, "a") as writer:
            writer.write(f'"f","{file.normalized_path()}","{file.hash}"\n')
