import hashlib
import os
import pathlib
import shutil
from uuid import uuid4
from zipfile import ZipFile, ZipInfo
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
        return False

    def put(
        self, origin_file: os.PathLike, restore_path: os.PathLike
    ) -> models.StoredFile:
        # TODO handle IO exceptions and cleanup

        def relative_dir_from_hash(filehash: str) -> str:
            return os.path.join(filehash[0], filehash[1], filehash[2], filehash[3])

        with open(origin_file, mode="rb") as f:
            sha1 = hashlib.sha1()
            temp_name = str(uuid4())
            absolute_temp_name = utils.relative_to_absolute_path(
                self._root_path, temp_name
            )

            is_compressed = self.is_compression_eligible(origin_file)
            if is_compressed:
                zip_archive = ZipFile(absolute_temp_name, "x")
                archive = None
            else:
                zip_archive = None
                archive = open(absolute_temp_name, "xb")

            parts_counter = 0
            while True:
                parts_counter = parts_counter + 1
                data = f.read(self._config.buffer_size)
                if not data:
                    break
                sha1.update(data)

                if is_compressed:
                    zipinfo = ZipInfo(f"part{str(parts_counter).rjust(4, '0')}")
                    zip_archive.writestr(zipinfo, data)
                else:
                    archive.write(data)

            hash = sha1.hexdigest()
            relative_dir = relative_dir_from_hash(hash)
            absolute_dir = utils.relative_to_absolute_path(
                self._root_path, relative_dir
            )

            if is_compressed:
                zip_archive.close()
                final_name = f"{hash}.zip"
            else:
                archive.close()
                final_name = hash

            stored_location = os.path.join(relative_dir, final_name)
            absolute_final_name = utils.relative_to_absolute_path(
                self._root_path, stored_location
            )

            os.makedirs(absolute_dir, exist_ok=True)
            if not os.path.exists(absolute_final_name):
                os.rename(absolute_temp_name, absolute_final_name)
            else:
                os.remove(absolute_temp_name)

            restore_path_normalized = utils.normalize_path(restore_path)
            return models.StoredFile(
                restore_path_normalized, hash, stored_location, is_compressed
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
