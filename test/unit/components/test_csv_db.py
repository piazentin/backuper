"""Tests for :class:`CsvDb` helpers that are not covered via :class:`CsvBackupDatabase`."""

from pathlib import Path

from backuper.components.csv_db import CsvDb
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
