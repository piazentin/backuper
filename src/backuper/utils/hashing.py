import hashlib
import os

from backuper import config


def compute_hash(
    file_path: os.PathLike, buffer_size: int = config.HASHING_BUFFER_SIZE
) -> str:
    # Tech debt: this hashes only the first `buffer_size` bytes, not the whole file.
    # Full-file SHA-1 would be stronger for integrity, but would not match digests
    # already stored in CSVs and blob paths for files larger than the buffer; fixing
    # that requires a versioned hash algorithm and a data migration.
    # Until then, keep this behavior identical to historical backups.
    with open(file_path, "rb") as file:
        data = file.read(buffer_size)
        sha1 = hashlib.sha1()
        sha1.update(data)
    return sha1.hexdigest()
