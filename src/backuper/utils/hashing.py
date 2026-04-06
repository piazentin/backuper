import hashlib
import os

from backuper import config


def compute_hash(
    file_path: os.PathLike, buffer_size: int = config.HASHING_BUFFER_SIZE
) -> str:
    # Legacy contract: one read of up to `buffer_size` bytes (not full-file SHA-1).
    # Matches existing CSV hashes; changing this would desync content-addressed blobs.
    with open(file_path, "rb") as file:
        data = file.read(buffer_size)
        sha1 = hashlib.sha1()
        sha1.update(data)
    return sha1.hexdigest()
