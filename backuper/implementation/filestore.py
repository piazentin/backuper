import hashlib
import os
import pathlib
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

    def put(self, origin_file: os.PathLike, restore_path: str) -> models.StoredFile:
        # TODO handle IO exceptions and cleanup

        def final_dir_from_hash(filehash: str) -> str:
            return os.path.join(
                self._root_path, filehash[0], filehash[1], filehash[2], filehash[3]
            )

        with open(origin_file, mode="rb") as f:
            sha1 = hashlib.sha1()
            temp_name = str(uuid4())
            absolute_temp_name = utils.relative_to_absolute_path(
                self._root_path, temp_name
            )
            if self.is_compression_eligible(origin_file):
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

                if zip_archive:
                    # TODO test if zipping/unzipping is working alright
                    zipinfo = ZipInfo(f"part{str(parts_counter).rjust(4, '0')}")
                    zip_archive.writestr(zipinfo, data)
                else:
                    archive.write(data)

            hash = sha1.hexdigest()
            final_dir = final_dir_from_hash(hash)

            if zip_archive:
                zip_archive.close()
                final_name = f"{hash}.zip"
            else:
                archive.close()
                final_name = hash

            locator = os.path.join(final_dir, final_name)
            absolute_final_name = utils.relative_to_absolute_path(
                self._root_path, locator
            )

            os.makedirs(final_dir, exist_ok=True)
            if not os.path.exists(absolute_final_name):
                os.rename(absolute_temp_name, absolute_final_name)
            else:
                os.remove(absolute_temp_name)

            return models.StoredFile(restore_path, hash, locator)
