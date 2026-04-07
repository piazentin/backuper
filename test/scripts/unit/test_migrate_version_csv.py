"""Unit tests for ``scripts.migrate_version_csv.migrate`` (legacy shapes, errors, idempotency)."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.migrate_version_csv.migrate import MigrateError, migrate_version_csv_text

_HELLO_SHA1 = "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"
_STORED = "a/a/f/4/aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"


def _data_root_with_blob(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    blob = data / _STORED
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(b"hello")
    return data


def test_migrate_three_column_file_row_enriches_from_blob(tmp_path: Path) -> None:
    data_root = _data_root_with_blob(tmp_path)
    text = f'"f","hello.txt","{_HELLO_SHA1}"\n'
    migrated, warnings = migrate_version_csv_text(
        text,
        data_root=data_root,
        version_path=Path("v.csv"),
    )
    assert '"f","hello.txt"' in migrated
    assert _STORED in migrated
    assert '"False"' in migrated
    assert '"5"' in migrated  # logical size of hello
    assert not warnings


def test_migrate_five_column_file_row(tmp_path: Path) -> None:
    data_root = _data_root_with_blob(tmp_path)
    text = f'"f","hello.txt","{_HELLO_SHA1}","{_STORED}","False"\n'
    migrated, warnings = migrate_version_csv_text(
        text,
        data_root=data_root,
        version_path=Path("v.csv"),
    )
    assert '"5"' in migrated
    assert not warnings


def test_migrate_seven_column_ignores_extra_columns(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    text = (
        f'"f","hello.txt","{_HELLO_SHA1}","{_STORED}","False","5","1.0",'
        f'"ignored","also"\n'
    )
    migrated, warnings = migrate_version_csv_text(
        text,
        data_root=data_root,
        version_path=Path("v.csv"),
    )
    assert "ignored" not in migrated
    assert "also" not in migrated
    assert migrated.endswith("\n")
    assert not warnings


def test_migrate_seven_column_empty_size_mtime_enriches(tmp_path: Path) -> None:
    data_root = _data_root_with_blob(tmp_path)
    text = f'"f","hello.txt","{_HELLO_SHA1}","{_STORED}","False","",""\n'
    migrated, warnings = migrate_version_csv_text(
        text,
        data_root=data_root,
        version_path=Path("v.csv"),
    )
    assert '"5"' in migrated
    assert not warnings


def test_migrate_directory_row_normalizes_slashes(tmp_path: Path) -> None:
    # Single backslash between segments becomes a forward slash after normalization.
    text = '"d","photos\\2024",""\n'
    migrated, warnings = migrate_version_csv_text(
        text,
        data_root=tmp_path / "data",
        version_path=Path("v.csv"),
    )
    assert migrated == '"d","photos/2024",""\n'
    assert not warnings


def test_migrate_canonical_round_trip_stable(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    text = f'"f","hello.txt","{_HELLO_SHA1}","{_STORED}","False","5","1712500000.0"\n'
    migrated, warnings = migrate_version_csv_text(
        text,
        data_root=data_root,
        version_path=Path("v.csv"),
    )
    assert migrated == text
    assert not warnings


def test_migrate_idempotent_second_pass_matches_first(tmp_path: Path) -> None:
    data_root = _data_root_with_blob(tmp_path)
    legacy = f'"f","hello.txt","{_HELLO_SHA1}"\n'
    first, _ = migrate_version_csv_text(
        legacy,
        data_root=data_root,
        version_path=Path("v.csv"),
    )
    second, w2 = migrate_version_csv_text(
        first,
        data_root=data_root,
        version_path=Path("v.csv"),
    )
    assert first == second
    assert not w2


def test_migrate_rejects_empty_row(tmp_path: Path) -> None:
    with pytest.raises(MigrateError, match="empty CSV row"):
        migrate_version_csv_text(
            "\n",
            data_root=tmp_path,
            version_path=Path("v.csv"),
        )


def test_migrate_rejects_unknown_kind(tmp_path: Path) -> None:
    with pytest.raises(MigrateError, match="unknown CSV row kind"):
        migrate_version_csv_text(
            '"x","a","b"\n',
            data_root=tmp_path,
            version_path=Path("v.csv"),
        )


def test_migrate_rejects_file_row_bad_column_count(tmp_path: Path) -> None:
    with pytest.raises(MigrateError, match="unsupported file row column count 4"):
        migrate_version_csv_text(
            '"f","a","b","c"\n',
            data_root=tmp_path,
            version_path=Path("v.csv"),
        )


def test_migrate_rejects_file_row_six_columns(tmp_path: Path) -> None:
    with pytest.raises(MigrateError, match="unsupported file row column count 6"):
        migrate_version_csv_text(
            '"f","a","b","c","d","e"\n',
            data_root=tmp_path,
            version_path=Path("v.csv"),
        )


def test_migrate_rejects_invalid_size_field(tmp_path: Path) -> None:
    with pytest.raises(MigrateError, match="invalid size field"):
        migrate_version_csv_text(
            f'"f","x","{_HELLO_SHA1}","{_STORED}","False","nope","1.0"\n',
            data_root=tmp_path,
            version_path=Path("v.csv"),
        )


def test_migrate_rejects_invalid_mtime_field(tmp_path: Path) -> None:
    with pytest.raises(MigrateError, match="invalid mtime field"):
        migrate_version_csv_text(
            f'"f","x","{_HELLO_SHA1}","{_STORED}","False","1","nope"\n',
            data_root=tmp_path,
            version_path=Path("v.csv"),
        )


def test_migrate_directory_row_too_short(tmp_path: Path) -> None:
    with pytest.raises(MigrateError, match="directory row needs at least 2"):
        migrate_version_csv_text(
            '"d"\n',
            data_root=tmp_path,
            version_path=Path("v.csv"),
        )


def test_migrate_missing_blob_warns_and_defaults_zero(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    text = f'"f","hello.txt","{_HELLO_SHA1}"\n'
    migrated, warnings = migrate_version_csv_text(
        text,
        data_root=data_root,
        version_path=Path("v.csv"),
    )
    assert '"0"' in migrated
    assert '"0.0"' in migrated or "0.0" in migrated
    assert len(warnings) == 1
    assert "no blob on disk" in warnings[0]
