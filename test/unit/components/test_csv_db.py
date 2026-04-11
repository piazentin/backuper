"""Tests for :class:`CsvDb` helpers that are not covered via :class:`CsvBackupDatabase`."""

import logging
from pathlib import Path

import pytest
from backuper.components.csv_db import CsvDb, _DirEntry, _StoredFile
from backuper.config import CsvDbConfig


def test_get_most_recent_version_empty_database(tmp_path: Path) -> None:
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    assert csv_db.get_most_recent_version() is None


def test_get_most_recent_version_single_version(tmp_path: Path) -> None:
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    csv_db.create_version("2026-04-11T120000")
    chosen = csv_db.get_most_recent_version()
    assert chosen is not None
    assert chosen.name == "2026-04-11T120000"


def test_get_most_recent_version_is_lexicographic_max_not_numeric(
    tmp_path: Path,
) -> None:
    """``v2`` > ``v10`` as strings; semantics are lexicographic, not semver-like."""
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    csv_db.create_version("v10")
    csv_db.create_version("v2")
    chosen = csv_db.get_most_recent_version()
    assert chosen is not None
    assert chosen.name == "v2"


def test_get_most_recent_version_lexicographic_among_several(tmp_path: Path) -> None:
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    for name in ("alpha", "beta", "gamma"):
        csv_db.create_version(name)
    chosen = csv_db.get_most_recent_version()
    assert chosen is not None
    assert chosen.name == "gamma"


def test_skips_empty_csv_rows_in_version_manifest(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Blank lines in a version CSV must not raise or break filtered reads."""
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    version = csv_db.create_version("v1")
    csv_db.insert_dir(version, _DirEntry("adir"))
    csv_db.insert_file(
        version,
        _StoredFile(
            restore_path="f.txt",
            sha1hash="abc",
            stored_location="0/1/2/3/abc",
            is_compressed=False,
            size=10,
            mtime=1.0,
        ),
    )
    manifest = csv_db._csv_path_from_name("v1")
    with open(manifest, "a", encoding="utf-8") as f:
        f.write("\n\n")

    with caplog.at_level(logging.WARNING):
        assert len(csv_db.get_fs_objects_for_version(version)) == 2
        assert len(csv_db.get_dirs_for_version(version)) == 1
        assert len(csv_db.get_files_for_version(version)) == 1

    assert "Skipping empty row" in caplog.text
    assert "v1" in caplog.text
