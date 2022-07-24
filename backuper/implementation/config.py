from dataclasses import dataclass


@dataclass
class CsvDbConfig:
    backup_dir: str
    csv_file_extension: str = ".csv"


@dataclass
class FilestoreConfig:
    backup_dir: str


ZIPFILE_EXT = ".zip"
HASHING_BUFFER_SIZE = 65536  # 64kb
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
}
ZIP_MIN_FILESIZE_IN_BYTES = 1024  # 1KB
