"""
Integration tests: legacy CSV manifests migrate to canonical shape and remain readable
by runtime ``CsvDb`` / ``check``-style flows.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from backuper.commands import CheckCommand
from backuper.components.csv_db import CsvDb, _StoredFile, _Version
from backuper.config import CsvDbConfig
from backuper.entrypoints.cli import run_check
from scripts.migrate_version_csv.__main__ import main
from scripts.migrate_version_csv.atomic_output import write_migrated_atomic
from scripts.migrate_version_csv.migrate import migrate_version_csv_text

_HELLO_SHA1 = "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"
_STORED = "a/a/f/4/aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"


def _write_blob(data_root: Path) -> None:
    blob = data_root / _STORED
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(b"hello")


def _csv_db(backup_root: Path) -> CsvDb:
    return CsvDb(CsvDbConfig(backup_dir=str(backup_root)))


@pytest.fixture
def backup_root(tmp_path: Path) -> Path:
    root = tmp_path / "backup"
    root.mkdir()
    (root / "db").mkdir()
    _write_blob(root / "data")
    return root


def test_migrate_three_column_then_csv_db_reads_files(backup_root: Path) -> None:
    csv_path = backup_root / "db" / "v1.csv"
    csv_path.write_text(
        f'"d","subdir",""\n"f","hello.txt","{_HELLO_SHA1}"\n',
        encoding="utf-8",
    )
    assert (
        main(
            [
                str(backup_root),
                "--csv",
                str(csv_path),
            ]
        )
        == 0
    )
    db = _csv_db(backup_root)
    files = db.get_files_for_version(_Version("v1"))
    assert len(files) == 1
    sf = files[0]
    assert isinstance(sf, _StoredFile)
    assert sf.restore_path == "hello.txt"
    assert sf.sha1hash == _HELLO_SHA1
    assert sf.stored_location.replace("\\", "/") == _STORED
    assert sf.is_compressed is False
    assert sf.size == 5
    dirs = db.get_dirs_for_version(_Version("v1"))
    assert len(dirs) == 1
    assert dirs[0].normalized_path() == "subdir"


def test_migrate_five_column_then_csv_db_reads_files(backup_root: Path) -> None:
    csv_path = backup_root / "db" / "v1.csv"
    csv_path.write_text(
        f'"f","hello.txt","{_HELLO_SHA1}","{_STORED}","False"\n',
        encoding="utf-8",
    )
    assert main([str(backup_root), "--csv", str(csv_path)]) == 0
    db = _csv_db(backup_root)
    files = db.get_files_for_version(_Version("v1"))
    assert len(files) == 1
    assert files[0].size == 5


def test_migrate_seven_column_extra_columns_ignored(backup_root: Path) -> None:
    csv_path = backup_root / "db" / "v1.csv"
    csv_path.write_text(
        f'"f","hello.txt","{_HELLO_SHA1}","{_STORED}","False","5","1.0",'
        f'"__extra_a__","__extra_b__"\n',
        encoding="utf-8",
    )
    assert main([str(backup_root), "--csv", str(csv_path)]) == 0
    text = csv_path.read_text(encoding="utf-8")
    assert "__extra_a__" not in text
    assert "__extra_b__" not in text
    db = _csv_db(backup_root)
    assert db.get_files_for_version(_Version("v1"))[0].size == 5


def test_migrate_idempotent_second_run_unchanged(backup_root: Path) -> None:
    csv_path = backup_root / "db" / "v1.csv"
    csv_path.write_text(f'"f","hello.txt","{_HELLO_SHA1}"\n', encoding="utf-8")
    assert main([str(backup_root), "--csv", str(csv_path)]) == 0
    first_bytes = csv_path.read_bytes()
    assert main([str(backup_root), "--csv", str(csv_path)]) == 0
    assert csv_path.read_bytes() == first_bytes


def test_migrate_dry_run_does_not_modify_file(backup_root: Path) -> None:
    csv_path = backup_root / "db" / "v1.csv"
    original = f'"f","hello.txt","{_HELLO_SHA1}"\n'
    csv_path.write_text(original, encoding="utf-8")
    assert (
        main(
            [
                str(backup_root),
                "--csv",
                str(csv_path),
                "--dry-run",
            ]
        )
        == 0
    )
    assert csv_path.read_text(encoding="utf-8") == original


def test_migrate_cli_reports_error_on_malformed_row(backup_root: Path) -> None:
    csv_path = backup_root / "db" / "v1.csv"
    csv_path.write_text('"f","a","b","c"\n', encoding="utf-8")
    assert main([str(backup_root), "--csv", str(csv_path)]) == 1


def test_run_check_succeeds_after_migration(backup_root: Path) -> None:
    csv_path = backup_root / "db" / "v1.csv"
    csv_path.write_text(f'"f","hello.txt","{_HELLO_SHA1}"\n', encoding="utf-8")
    assert main([str(backup_root), "--csv", str(csv_path)]) == 0
    run_check(CheckCommand(location=str(backup_root), version="v1"))


def test_write_migrated_atomic_idempotent_on_canonical_text(
    tmp_path: Path,
) -> None:
    """Second write of already-canonical content is ``unchanged`` (no extra .bak)."""
    csv_path = tmp_path / "v.csv"
    canonical = f'"f","hello.txt","{_HELLO_SHA1}","{_STORED}","False","5","1.0"\n'
    csv_path.write_text(canonical, encoding="utf-8")
    migrated, _ = migrate_version_csv_text(
        canonical,
        data_root=tmp_path / "data",
        version_path=csv_path,
    )
    assert write_migrated_atomic(csv_path, migrated, dry_run=False) == "unchanged"
    assert not (tmp_path / "v.csv.bak").exists()
