from abc import ABC
import os
from typing import List
from backuper.implementation.config import CsvDbConfig
import backuper.implementation.models as models


class CsvDb:
    def __init__(self, config: CsvDbConfig) -> None:
        self._config = config

    def get_all_versions(self) -> List[models.Version]:
        return [
            models.Version(f.strip(self._config.csv_file_extension))
            for f in os.listdir(self._config.backup_dir)
            if f.endswith(self._config.csv_file_extension)
        ]
