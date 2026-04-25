from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from backuper.config import SqliteDbConfig
from backuper.utils.paths import normalize_path


@dataclass(frozen=True)
class _DirEntry:
    name: str

    def normalized_path(self) -> str:
        return normalize_path(self.name)


@dataclass(frozen=True)
class _StoredFile:
    restore_path: str
    sha1hash: str
    stored_location: str
    is_compressed: bool
    size: int = 0
    mtime: float = 0.0


stored_text_file1 = _StoredFile(
    "text_file1.txt",
    "fef9161f9f9a492dba2b1357298f17897849fefc",
    "f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
    False,
)
stored_text_file1_copy = _StoredFile(
    "text_file1 copy.txt",
    "fef9161f9f9a492dba2b1357298f17897849fefc",
    "f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
    False,
)
stored_text_file1_copy_updated = _StoredFile(
    "text_file1 copy.txt",
    "7f2f5c0211b62cc0f2da98c3f253bba9dc535b17",
    "7/f/2/f/7f2f5c0211b62cc0f2da98c3f253bba9dc535b17",
    False,
)
stored_starry_night = _StoredFile(
    "subdir/starry_night.png",
    "07c8762861e8f1927708408702b1fd747032f050",
    "0/7/c/8/07c8762861e8f1927708408702b1fd747032f050",
    False,
)
stored_license = _StoredFile(
    "LICENSE",
    "10e4b6f822c7493e1aea22d15e515b584b2db7a2",
    "1/0/e/4/10e4b6f822c7493e1aea22d15e515b584b2db7a2",
    False,
)
stored_license_updated = _StoredFile(
    "LICENSE",
    "5b5174193c004d8f27811b961fbaa545b5460f2a",
    "5/b/5/1/5b5174193c004d8f27811b961fbaa545b5460f2a",
    False,
)
stored_license_zip = _StoredFile(
    "LICENSE",
    "10e4b6f822c7493e1aea22d15e515b584b2db7a2",
    "1/0/e/4/10e4b6f822c7493e1aea22d15e515b584b2db7a2.zip",
    True,
)
stored_license_zip_updated = _StoredFile(
    "LICENSE",
    "5b5174193c004d8f27811b961fbaa545b5460f2a",
    "5/b/5/1/5b5174193c004d8f27811b961fbaa545b5460f2a.zip",
    True,
)

new_backup_stored_files = {
    stored_text_file1,
    stored_text_file1_copy,
    stored_starry_night,
    stored_license,
}
new_backup_stored_files_zip = {
    stored_text_file1,
    stored_text_file1_copy,
    stored_starry_night,
    stored_license_zip,
}
update_stored_files = {
    stored_text_file1,
    stored_text_file1_copy_updated,
    stored_license_updated,
}
update_stored_files_zip = {
    stored_text_file1,
    stored_text_file1_copy_updated,
    stored_license_zip_updated,
}

new_backup_dirs = {_DirEntry("subdir"), _DirEntry("subdir/empty dir")}
update_dirs: set[_DirEntry] = set()

new_backup_db = {
    "dirs": new_backup_dirs,
    "stored_files": new_backup_stored_files,
}
new_backup_with_zip_db = {
    "dirs": new_backup_dirs,
    "stored_files": new_backup_stored_files_zip,
}
update_backup = {
    "dirs": update_dirs,
    "stored_files": update_stored_files,
}
update_backup_with_zip = {"dirs": update_dirs, "stored_files": update_stored_files_zip}


def _stored_file_matches_row(stored: _StoredFile, row: sqlite3.Row) -> bool:
    row_restore_path = normalize_path(str(row["restore_path"]))
    expected_restore_path = normalize_path(stored.restore_path)
    loc = str(row["storage_location"]).replace("\\", "/")
    exp_loc = stored.stored_location.replace("\\", "/")
    is_zip = str(row["compression"]) == "zip"
    return (
        row_restore_path == expected_restore_path
        and str(row["hash_digest"]) == stored.sha1hash
        and loc == exp_loc
        and is_zip == stored.is_compressed
    )


def assert_sqlite_manifest_matches_fixture(
    backup_root: Path | str,
    version_name: str,
    expected: dict[str, set[_DirEntry] | set[_StoredFile]],
) -> None:
    """Assert ``manifest.sqlite3`` content for ``version_name`` matches fixture sets."""
    root = Path(backup_root)
    cfg = SqliteDbConfig(backup_dir=str(root))
    db_path = root / cfg.backup_db_dir / cfg.sqlite_filename
    assert db_path.is_file(), f"expected SQLite manifest at {db_path}"

    expected_dirs = expected["dirs"]
    expected_files = expected["stored_files"]
    assert isinstance(expected_dirs, set)
    assert isinstance(expected_files, set)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        dir_rows = conn.execute(
            """
            SELECT restore_path FROM version_directories
            WHERE version_name = ? ORDER BY id
            """,
            (version_name,),
        ).fetchall()
        file_rows = conn.execute(
            """
            SELECT restore_path, hash_digest, storage_location, compression, size, mtime
            FROM version_files
            WHERE version_name = ? ORDER BY id
            """,
            (version_name,),
        ).fetchall()

    got_dir_norms = {normalize_path(str(r["restore_path"])) for r in dir_rows}
    expected_dir_norms = {d.normalized_path() for d in expected_dirs}
    assert got_dir_norms == expected_dir_norms

    assert len(file_rows) == len(expected_files)
    for row in file_rows:
        if not any(_stored_file_matches_row(sf, row) for sf in expected_files):
            raise AssertionError(f"unexpected manifest file row {dict(row)}")
