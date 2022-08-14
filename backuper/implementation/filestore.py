import os
import pathlib
import shutil
from typing import Optional
import backuper.implementation.analyze as analyze
from zipfile import ZipFile
from backuper.implementation import models, utils
from backuper.implementation.config import FilestoreConfig


def relative_dir_from_hash(filehash: str) -> str:
    return os.path.join(filehash[0], filehash[1], filehash[2], filehash[3])


def hash_to_stored_location(filehash: str, is_compressed: bool) -> os.PathLike:
    if is_compressed:
        final_name = f"{filehash}.zip"
    else:
        final_name = filehash
    relative_dir = relative_dir_from_hash(filehash)
    return os.path.join(relative_dir, final_name)


class Filestore:
    def __init__(self, config: FilestoreConfig) -> None:
        self._config = config
        self._root_path = utils.relative_to_absolute_path(
            self._config.backup_dir, self._config.backup_data_dir
        )
        os.makedirs(self._root_path, exist_ok=True)

    def is_compression_eligible(
        self, origin_file: os.PathLike, size: Optional[int] = None
    ) -> bool:
        ext = pathlib.Path(origin_file).suffix

        if size is None:
            size = os.path.getsize(origin_file)

        return (
            self._config.zip_enabled
            and ext not in self._config.zip_skip_extensions
            and size > self._config.zip_min_filesize_in_bytes
        )

    def exists(self, stored_location: models.StoredLocation) -> bool:
        absolute_location = os.path.join(self._root_path, stored_location)
        return os.path.exists(absolute_location)

    def analyze_file_to_stored_file(
        self, analyze_file: analyze.File
    ) -> models.StoredFile:
        is_compressed = self.is_compression_eligible(
            analyze_file.absolute_path, size=analyze_file.size
        )
        return models.StoredFile(
            utils.normalize_path(analyze_file.relative_path),
            analyze_file.hash,
            hash_to_stored_location(analyze_file.hash, is_compressed),
            is_compressed,
        )

    def put(
        self,
        origin_file: os.PathLike,
        restore_path: os.PathLike,
        precomputed_hash: Optional[str] = None,
    ) -> models.StoredFile:
        # TODO handle IO exceptions and cleanup
        restore_path_normalized = utils.normalize_path(restore_path)

        if precomputed_hash is not None:
            hash = precomputed_hash
        else:
            hash = utils.compute_hash(origin_file)

        is_compressed = self.is_compression_eligible(origin_file)
        stored_location = hash_to_stored_location(hash, is_compressed)
        if self.exists(stored_location):
            return models.StoredFile(
                restore_path_normalized,
                hash,
                stored_location,
                is_compressed,
            )

        absolute_temp_name = utils.relative_to_absolute_path(self._root_path, hash)
        if is_compressed:
            with ZipFile(absolute_temp_name, "x") as zip_archive:
                zip_archive.write(origin_file, "part001")
        else:
            shutil.copyfile(origin_file, absolute_temp_name)

        relative_dir = relative_dir_from_hash(hash)
        absolute_dir = utils.relative_to_absolute_path(self._root_path, relative_dir)

        absolute_final_name = utils.relative_to_absolute_path(
            self._root_path, stored_location
        )

        os.makedirs(absolute_dir, exist_ok=True)
        if not os.path.exists(absolute_final_name):
            os.rename(absolute_temp_name, absolute_final_name)
        else:
            os.remove(absolute_temp_name)

        return models.StoredFile(
            restore_path_normalized,
            hash,
            stored_location,
            is_compressed,
        )

    def restore(
        self, stored_file: models.StoredFile, restore_to_path: os.PathLike
    ) -> None:
        absolute_stored_location = utils.relative_to_absolute_path(
            self._root_path, stored_file.stored_location
        )
        absolute_restored_location = utils.relative_to_absolute_path(
            restore_to_path, stored_file.restore_path
        )

        os.makedirs(os.path.dirname(absolute_restored_location), exist_ok=True)

        if stored_file.is_compressed:
            with ZipFile(absolute_stored_location, "r") as zipfile, open(
                absolute_restored_location, "wb"
            ) as restored:
                for name in sorted(zipfile.namelist()):
                    restored.write(zipfile.read(name))
        else:
            shutil.copyfile(absolute_stored_location, absolute_restored_location)
