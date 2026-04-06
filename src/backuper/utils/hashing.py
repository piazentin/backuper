import hashlib
import os

from backuper import config


def compute_hash(
    file_path: os.PathLike, buffer_size: int = config.HASHING_BUFFER_SIZE
) -> str:
    sha1 = hashlib.sha1()
    with open(file_path, "rb") as file:
        while True:
            data = file.read(buffer_size)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()
