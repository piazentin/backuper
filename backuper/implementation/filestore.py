from backuper.implementation.config import FilestoreConfig


class Filestore:
    def __init__(self, config: FilestoreConfig) -> None:
        self._config = config
