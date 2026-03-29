import hashlib
import os

from backuper.implementation import config


def normalize_path(path: str) -> str:
    return "/".join(path.replace("\\", "/").strip("/").split("/"))


def compute_hash(
    file_path: os.PathLike, buffer_size: int = config.HASHING_BUFFER_SIZE
) -> str:
    with open(file_path, "rb") as file:
        data = file.read(buffer_size)
        sha1 = hashlib.sha1()
        sha1.update(data)
    return sha1.hexdigest()
