import os
from dataclasses import dataclass, field

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


BACKUPER_SQLITE_SYNCHRONOUS_ENV = "BACKUPER_SQLITE_SYNCHRONOUS"

_SQLITE_SYNCHRONOUS_SYMBOLIC = {"off": 0, "normal": 1, "full": 2, "extra": 3}


def _parse_sqlite_synchronous_pragma(raw: str) -> int:
    stripped = raw.strip()
    if not stripped:
        raise ValueError("value must not be empty")
    lowered = stripped.lower()
    if lowered in _SQLITE_SYNCHRONOUS_SYMBOLIC:
        return _SQLITE_SYNCHRONOUS_SYMBOLIC[lowered]
    try:
        n = int(stripped, 10)
    except ValueError as exc:
        raise ValueError("expected OFF, NORMAL, FULL, EXTRA, or integer 0–3") from exc
    if n < 0 or n > 3:
        raise ValueError(f"integer synchronous mode must be 0–3, got {n}")
    return n


def sqlite_synchronous_from_environment() -> int:
    """PRAGMA synchronous value (0–3) from ``BACKUPER_SQLITE_SYNCHRONOUS``, default NORMAL (1)."""
    raw = os.environ.get(BACKUPER_SQLITE_SYNCHRONOUS_ENV)
    if raw is None or not raw.strip():
        return 1
    try:
        return _parse_sqlite_synchronous_pragma(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid {BACKUPER_SQLITE_SYNCHRONOUS_ENV}={raw!r}: {exc.args[0]}. "
            "Use OFF, NORMAL, FULL, EXTRA, or 0–3."
        ) from exc


@dataclass
class SqliteDbConfig:
    backup_dir: str
    backup_db_dir: str = "db"
    sqlite_filename: str = "manifest.sqlite3"
    sqlite_synchronous: int = 1  # PRAGMA synchronous: 0–3 (OFF..EXTRA)


def sqlite_db_config(backup_dir: str) -> SqliteDbConfig:
    """Build manifest DB config with environment-derived ``sqlite_synchronous``."""
    return SqliteDbConfig(
        backup_dir=backup_dir,
        sqlite_synchronous=sqlite_synchronous_from_environment(),
    )


@dataclass
class FilestoreConfig:
    backup_dir: str
    backup_data_dir: str = "data"
    zip_enabled: bool = ZIP_ENABLED
    zip_min_filesize_in_bytes: int = ZIP_MIN_FILESIZE_IN_BYTES
    zip_skip_extensions: set[str] = field(default_factory=lambda: ZIP_SKIP_EXTENSIONS)
