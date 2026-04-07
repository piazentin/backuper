"""Unit tests for ``scripts.migrate_version_csv.atomic_output``."""

from __future__ import annotations

from pathlib import Path

from scripts.migrate_version_csv.atomic_output import (
    allocate_rollback_copy_path,
    write_migrated_atomic,
)


def test_allocate_rollback_copy_path_primary(tmp_path: Path) -> None:
    csv_path = tmp_path / "v1.csv"
    csv_path.write_text("a", encoding="utf-8")
    assert allocate_rollback_copy_path(csv_path) == tmp_path / "v1.csv.bak"


def test_allocate_rollback_copy_path_bumps_when_bak_exists(tmp_path: Path) -> None:
    csv_path = tmp_path / "v1.csv"
    csv_path.write_text("a", encoding="utf-8")
    (tmp_path / "v1.csv.bak").write_text("old", encoding="utf-8")
    assert allocate_rollback_copy_path(csv_path) == tmp_path / "v1.csv.bak.1"


def test_allocate_rollback_copy_path_bumps_sequence(tmp_path: Path) -> None:
    csv_path = tmp_path / "v1.csv"
    csv_path.write_text("a", encoding="utf-8")
    (tmp_path / "v1.csv.bak").write_text("x", encoding="utf-8")
    (tmp_path / "v1.csv.bak.1").write_text("y", encoding="utf-8")
    assert allocate_rollback_copy_path(csv_path) == tmp_path / "v1.csv.bak.2"


def test_write_migrated_atomic_unchanged_when_bytes_equal(tmp_path: Path) -> None:
    csv_path = tmp_path / "v.csv"
    content = '"f","a","b","c","False","0","0.0"\n'
    csv_path.write_text(content, encoding="utf-8")
    assert write_migrated_atomic(csv_path, content, dry_run=False) == "unchanged"


def test_write_migrated_atomic_dry_run_would_change(tmp_path: Path) -> None:
    csv_path = tmp_path / "v.csv"
    csv_path.write_text("old", encoding="utf-8")
    assert write_migrated_atomic(csv_path, "new", dry_run=True) == "would_change"
    assert csv_path.read_text(encoding="utf-8") == "old"


def test_write_migrated_atomic_replaced_creates_rollback_and_updates(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "v.csv"
    csv_path.write_text("old", encoding="utf-8")
    new_text = '"f","p","h","l","False","1","2.0"\n'
    assert write_migrated_atomic(csv_path, new_text, dry_run=False) == "replaced"
    assert csv_path.read_text(encoding="utf-8") == new_text
    bak = tmp_path / "v.csv.bak"
    assert bak.is_file()
    assert bak.read_text(encoding="utf-8") == "old"
