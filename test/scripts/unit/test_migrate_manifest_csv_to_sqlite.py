"""Unit tests for ``scripts.migrate_manifest_csv_to_sqlite`` (discovery, CLI, stub main)."""

from __future__ import annotations

import argparse
import io
from pathlib import Path

import pytest
from backuper.models import MalformedBackupCsvError
from scripts.migrate_manifest_csv_to_sqlite.__main__ import _parse_args, main
from scripts.migrate_manifest_csv_to_sqlite.canonical_parse import (
    CanonicalCsvDir,
    CanonicalCsvFile,
    parse_canonical_version_csv,
)
from scripts.migrate_manifest_csv_to_sqlite.discovery import discover_csv_manifests


def test_discover_empty_when_db_missing(tmp_path: Path) -> None:
    root = tmp_path / "backup"
    root.mkdir()
    assert discover_csv_manifests(root, "db") == []


def test_discover_sorted_csv_only_excludes_dotfiles(tmp_path: Path) -> None:
    db = tmp_path / "db"
    db.mkdir(parents=True)
    (db / "z.csv").write_text("x", encoding="utf-8")
    (db / "a.csv").write_text("x", encoding="utf-8")
    (db / "._skip.csv").write_text("x", encoding="utf-8")
    (db / ".pending__x.csv").write_text("x", encoding="utf-8")
    (db / "readme.txt").write_text("x", encoding="utf-8")
    (db / "nested").mkdir()
    found = discover_csv_manifests(tmp_path, "db")
    assert found == [db / "a.csv", db / "z.csv"]


def test_parse_args_defaults(tmp_path: Path) -> None:
    ns = _parse_args([str(tmp_path)])
    assert ns.backup_root == tmp_path
    assert ns.db_dir == "db"
    assert ns.data_dir == "data"
    assert ns.csv is None
    assert ns.dry_run is False
    assert ns.force is False
    assert ns.verbose is False


def test_parse_args_csv_repeatable_and_flags(tmp_path: Path) -> None:
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    ns = _parse_args(
        [
            str(tmp_path),
            "--db-dir",
            "manifests",
            "--data-dir",
            "blobs",
            "--csv",
            str(a),
            "--csv",
            str(b),
            "--dry-run",
            "--force",
            "-v",
        ]
    )
    assert ns.db_dir == "manifests"
    assert ns.data_dir == "blobs"
    assert ns.csv == [a, b]
    assert ns.dry_run is True
    assert ns.force is True
    assert ns.verbose is True


def test_help_epilog_mentions_runbook_tbd() -> None:
    from scripts.migrate_manifest_csv_to_sqlite import __main__ as mm

    buf = io.StringIO()
    p = argparse.ArgumentParser(
        description="x",
        epilog=mm._RUNBOOK_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("backup_root", type=Path)
    p.print_help(file=buf)
    text = buf.getvalue()
    assert "docs/csv-to-sqlite-migration.md" in text
    assert "verify-integrity" in text


def test_main_no_manifests_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "db").mkdir()
    assert main([str(tmp_path)]) == 0
    err = capsys.readouterr().err
    assert "No CSV manifest files found" in err


def test_main_dry_run_lists_targets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "db"
    db.mkdir()
    (db / "v.csv").write_text('"d","x",""\n', encoding="utf-8")
    assert main([str(tmp_path), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Dry-run" in out
    assert "v.csv" in out


def test_main_apply_stub_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "db"
    db.mkdir()
    (db / "v.csv").write_text('"d","x",""\n', encoding="utf-8")
    assert main([str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "not implemented" in err.lower()


def test_main_explicit_csv_dry_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    csv_path = tmp_path / "elsewhere.csv"
    csv_path.write_text('"d","x",""\n', encoding="utf-8")
    assert main([str(tmp_path), "--csv", str(csv_path), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert str(csv_path.resolve()) in out


def test_parse_canonical_minimal_dirs_and_files(tmp_path: Path) -> None:
    p = tmp_path / "v.csv"
    p.write_text(
        '"d","photos/2024",""\n'
        '"f","docs/readme.txt","abc","aa/bb/abc.zip","False","1234","1712500000.0"\n',
        encoding="utf-8",
    )
    objs = parse_canonical_version_csv(p)
    assert len(objs) == 2
    assert isinstance(objs[0], CanonicalCsvDir)
    assert objs[0].name == "photos/2024"
    assert isinstance(objs[1], CanonicalCsvFile)
    assert objs[1].restore_path == "docs/readme.txt"
    assert objs[1].sha1hash == "abc"
    assert objs[1].stored_location == "aa/bb/abc.zip"
    assert objs[1].is_compressed is False
    assert objs[1].size == 1234
    assert objs[1].mtime == 1712500000.0


def test_parse_canonical_rejects_legacy_short_file_row(tmp_path: Path) -> None:
    p = tmp_path / "legacy.csv"
    p.write_text('"f","a.txt","hashonly"\n', encoding="utf-8")
    with pytest.raises(MalformedBackupCsvError) as ei:
        parse_canonical_version_csv(p)
    msg = str(ei.value)
    assert "legacy short file row" in msg
    assert "migrate_version_csv" in msg
    assert "CSV record 1" in msg


def test_parse_canonical_rejects_unknown_row_kind(tmp_path: Path) -> None:
    p = tmp_path / "bad.csv"
    p.write_text('"x","nope",""\n', encoding="utf-8")
    with pytest.raises(MalformedBackupCsvError) as ei:
        parse_canonical_version_csv(p)
    assert "Unknown CSV row type" in str(ei.value)
    assert "migrate_version_csv" in str(ei.value)


def test_parse_canonical_error_includes_manifest_path(tmp_path: Path) -> None:
    p = tmp_path / "bad.csv"
    p.write_text('"d","only",""\n"q","bad",""\n', encoding="utf-8")
    with pytest.raises(MalformedBackupCsvError) as ei:
        parse_canonical_version_csv(p)
    assert str(p) in str(ei.value)
    assert "CSV record 2" in str(ei.value)


def test_parse_canonical_empty_file_returns_empty(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8")
    with caplog.at_level("WARNING"):
        assert parse_canonical_version_csv(p) == []
    assert "empty" in caplog.text.lower()


def test_main_invalid_manifest_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "db"
    db.mkdir()
    (db / "bad.csv").write_text('"f","only","three"\n', encoding="utf-8")
    assert main([str(tmp_path), "--dry-run"]) == 1
    err = capsys.readouterr().err
    assert "ERROR:" in err
    assert "migrate_version_csv" in err
