from __future__ import annotations

import os
import pathlib
import shutil
from pathlib import Path
from zipfile import ZipFile

from backuper.config import FilestoreConfig
from backuper.interfaces import FileStore, PutResult
from backuper.utils.hashing import compute_hash
from backuper.utils.paths import hash_to_stored_location, normalize_path

StoredLocation = str


class LocalFileStore(FileStore):
    def __init__(self, config: FilestoreConfig) -> None:
        self._config = config
        self._root_path = Path(self._config.backup_dir) / self._config.backup_data_dir
        self._root_path.mkdir(parents=True, exist_ok=True)

    def is_compression_eligible(
        self, origin_file: os.PathLike, size: int | None = None
    ) -> bool:
        ext = pathlib.Path(origin_file).suffix
        file_size = os.path.getsize(origin_file) if size is None else size
        return (
            self._config.zip_enabled
            and ext not in self._config.zip_skip_extensions
            and file_size > self._config.zip_min_filesize_in_bytes
        )

    def exists(self, stored_location: StoredLocation) -> bool:
        return (self._root_path / stored_location).exists()

    def blob_relative_path(self, file_hash: str, is_compressed: bool) -> str:
        return str(hash_to_stored_location(file_hash, is_compressed))

    def blob_exists(self, file_hash: str, is_compressed: bool) -> bool:
        return self.exists(self.blob_relative_path(file_hash, is_compressed))

    def read_blob(self, file_hash: str, is_compressed: bool) -> bytes:
        rel = self.blob_relative_path(file_hash, is_compressed)
        path = self._root_path / rel
        if is_compressed:
            with ZipFile(path, "r") as zf:
                return zf.read("part001")
        return path.read_bytes()

    def put(
        self,
        origin_file: os.PathLike[str],
        restore_path: Path,
        precomputed_hash: str | None = None,
    ) -> PutResult:
        file_hash = precomputed_hash or compute_hash(origin_file)
        is_compressed = self.is_compression_eligible(origin_file)
        stored_location = str(hash_to_stored_location(file_hash, is_compressed))
        restore_path_normalized = normalize_path(str(restore_path))

        if self.exists(stored_location):
            return PutResult(
                restore_path=restore_path_normalized,
                hash=file_hash,
                stored_location=stored_location,
                is_compressed=is_compressed,
            )

        staged_blob_path = self._root_path / file_hash
        if is_compressed:
            with ZipFile(staged_blob_path, "x") as zip_archive:
                zip_archive.write(origin_file, "part001")
        else:
            shutil.copyfile(origin_file, staged_blob_path)

        content_address_path = self._root_path / stored_location
        self._publish_staged_blob_if_absent(staged_blob_path, content_address_path)

        return PutResult(
            restore_path=restore_path_normalized,
            hash=file_hash,
            stored_location=stored_location,
            is_compressed=is_compressed,
        )

    def _publish_staged_blob_if_absent(
        self, staged_blob_path: Path, content_address_path: Path
    ) -> None:
        content_address_path.parent.mkdir(parents=True, exist_ok=True)

        # Publish staged content once under the content-addressed path.
        # If another writer already published the same hash, discard ours.
        if not content_address_path.exists():
            os.rename(staged_blob_path, content_address_path)
        else:
            os.remove(staged_blob_path)
