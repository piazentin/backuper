import hashlib
import os
import pathlib
import shutil
from zipfile import ZipFile
from backuper.implementation import models, utils
from backuper.implementation.config import FilestoreConfig


class Filestore:
    def __init__(self, config: FilestoreConfig) -> None:
        self._config = config
        self._root_path = utils.relative_to_absolute_path(
            self._config.backup_dir, self._config.backup_data_dir
        )
        os.makedirs(self._root_path, exist_ok=True)

    def is_compression_eligible(self, origin_file: os.PathLike) -> bool:
        ext = pathlib.Path(origin_file).suffix
        size = os.path.getsize(origin_file)
        return (
            self._config.zip_enabled
            and ext not in self._config.zip_skip_extensions
            and size > self._config.zip_min_filesize_in_bytes
        )

    def exists(self, stored_location: models.StoredLocation) -> bool:
        absolute_location = os.path.join(self._root_path, stored_location)
        return os.path.exists(absolute_location)

    def compute_hash(self, origin_file: os.PathLike) -> str:
        with open(origin_file, "rb") as f:
            data = f.read(self._config.buffer_size)
            sha1 = hashlib.sha1()
            sha1.update(data)
        return sha1.hexdigest()

    def put(
        self, origin_file: os.PathLike, restore_path: os.PathLike
    ) -> models.StoredFile:
        # TODO handle IO exceptions and cleanup

        def relative_dir_from_hash(filehash: str) -> str:
            return os.path.join(filehash[0], filehash[1], filehash[2], filehash[3])

        def hash_to_stored_location(filehash: str, is_compressed: bool) -> os.PathLike:
            if is_compressed:
                final_name = f"{filehash}.zip"
            else:
                final_name = filehash
            relative_dir = relative_dir_from_hash(filehash)
            return os.path.join(relative_dir, final_name)

        restore_path_normalized = utils.normalize_path(restore_path)

        hash = self.compute_hash(origin_file)
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
