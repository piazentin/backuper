from dataclasses import dataclass, field
from typing import Set

ZIPFILE_EXT = ".zip"
ZIP_ENABLED = True
HASHING_BUFFER_SIZE = 52428800  # 50mb
ZIP_SKIP_EXTENSIONS = {
    ".mp3",
    ".ogg",
    ".wma",
    ".7z",
    ".arj",
    ".deb",
    ".pkg",
    ".rar",
    ".rpm",
    ".gz",
    ".zip",
    ".jar",
    ".jpg",
    ".jpeg",
    ".png",
    ".pptx",
    ".xlsx",
    ".docx",
    ".mp4",
    ".avi",
    ".mov",
    ".rm",
    ".mkv",
    ".wmv",
    ".tar.xz",
}
ZIP_MIN_FILESIZE_IN_BYTES = 1024  # 1KB


@dataclass
class CsvDbConfig:
    backup_dir: str
    backup_db_dir: str = "db"
    csv_file_extension: str = ".csv"


@dataclass
class FilestoreConfig:
    backup_dir: str
    backup_data_dir: str = "data"
    zip_enabled: bool = ZIP_ENABLED
    zip_min_filesize_in_bytes: int = ZIP_MIN_FILESIZE_IN_BYTES
    zip_skip_extensions: Set[str] = field(default_factory=lambda: ZIP_SKIP_EXTENSIONS)
