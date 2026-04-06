from __future__ import annotations

import os

from backuper.config import ZIPFILE_EXT


def normalize_path(path: str) -> str:
    return "/".join(path.replace("\\", "/").strip("/").split("/"))


def relative_dir_from_hash(filehash: str) -> str:
    return os.path.join(filehash[0], filehash[1], filehash[2], filehash[3])


def hash_to_stored_location(filehash: str, is_compressed: bool) -> str:
    final_name = f"{filehash}{ZIPFILE_EXT}" if is_compressed else filehash
    return os.path.join(relative_dir_from_hash(filehash), final_name)
