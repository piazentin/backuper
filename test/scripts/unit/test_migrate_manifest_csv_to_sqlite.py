"""Unit tests for ``scripts.migrate_manifest_csv_to_sqlite``."""

from __future__ import annotations

import argparse
import io
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import pytest
from backuper.models import MalformedBackupCsvError
from scripts.migrate_manifest_csv_to_sqlite.__main__ import _parse_args, main
from scripts.migrate_manifest_csv_to_sqlite.canonical_parse import (
    CanonicalCsvDir,
    CanonicalCsvFile,
    parse_canonical_version_csv,
)
from scripts.migrate_manifest_csv_to_sqlite.created_at import (
    infer_created_at_for_manifests,
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


def test_help_epilog_mentions_runbook() -> None:
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
    assert "TBD" not in text


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


def test_main_rejects_dot_prefixed_explicit_csv(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "db"
    db.mkdir()
    pending = db / ".pending__v.csv"
    pending.write_text('"d","x",""\n', encoding="utf-8")
    assert main([str(tmp_path), "--csv", str(pending)]) == 1
    err = capsys.readouterr().err
    assert "dot-prefixed" in err
    assert not (db / "manifest.sqlite3").exists()


def test_main_apply_writes_live_sqlite_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "db"
    db.mkdir()
    (tmp_path / "data").mkdir()
    (db / "v.csv").write_text(
        '"f","f.txt","abc","aa/bb/abc.zip","False","3","1.0"\n"d","dir/",""\n',
        encoding="utf-8",
    )
    assert main([str(tmp_path)]) == 0
    assert capsys.readouterr().err == ""
    live_db = db / "manifest.sqlite3"
    assert live_db.exists()
    assert not Path(f"{db / 'manifest.sqlite3.migrating'}-wal").exists()
    assert not Path(f"{db / 'manifest.sqlite3.migrating'}-shm").exists()
    with sqlite3.connect(live_db) as conn:
        user_version = conn.execute("PRAGMA user_version").fetchone()
        assert user_version is not None
        assert int(user_version[0]) == 1
        versions = conn.execute(
            "SELECT name, state FROM versions ORDER BY name ASC"
        ).fetchall()
        assert versions == [("v", "completed")]
        created_row = conn.execute(
            "SELECT created_at FROM versions WHERE name = 'v'"
        ).fetchone()
        assert created_row is not None
        assert created_row[0] < 1e11

        file_rows = conn.execute(
            "SELECT restore_path FROM version_files WHERE version_name = 'v' ORDER BY id ASC"
        ).fetchall()
        dir_rows = conn.execute(
            "SELECT restore_path FROM version_directories WHERE version_name = 'v' ORDER BY id ASC"
        ).fetchall()
        assert file_rows == [("f.txt",)]
        assert dir_rows == [("dir",)]


def test_main_explicit_csv_dry_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "db"
    db.mkdir()
    csv_path = db / "elsewhere.csv"
    csv_path.write_text('"d","x",""\n', encoding="utf-8")
    assert main([str(tmp_path), "--csv", str(csv_path), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert str(csv_path.resolve()) in out


def test_main_refuses_when_live_manifest_exists_without_force(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "db"
    db.mkdir()
    (tmp_path / "data").mkdir()
    (db / "v.csv").write_text('"d","x",""\n', encoding="utf-8")
    (db / "manifest.sqlite3").write_text("existing", encoding="utf-8")

    assert main([str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "already exists" in err
    assert "--force" in err


def test_main_force_rebuilds_existing_live_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "db"
    db.mkdir()
    (tmp_path / "data").mkdir()
    (db / "v.csv").write_text('"d","x",""\n', encoding="utf-8")
    live_db = db / "manifest.sqlite3"
    live_db.write_text("old-content", encoding="utf-8")

    assert main([str(tmp_path), "--force"]) == 0
    assert capsys.readouterr().err == ""
    with sqlite3.connect(live_db) as conn:
        versions = conn.execute("SELECT name, state FROM versions").fetchall()
        assert versions == [("v", "completed")]


def test_main_dry_run_leaves_no_sqlite_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "db"
    db.mkdir()
    (db / "v.csv").write_text('"d","x",""\n', encoding="utf-8")
    assert main([str(tmp_path), "--dry-run"]) == 0
    _ = capsys.readouterr()
    assert not (db / "manifest.sqlite3").exists()
    assert not (db / "manifest.sqlite3.migrating").exists()


def test_main_rejects_explicit_csv_outside_selected_db_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup_root = tmp_path / "backup"
    db1 = backup_root / "db1"
    db2 = backup_root / "db2"
    db1.mkdir(parents=True)
    db2.mkdir(parents=True)
    (backup_root / "data").mkdir()
    first = db1 / "same.csv"
    second = db2 / "same.csv"
    first.write_text('"d","x",""\n', encoding="utf-8")
    second.write_text('"d","y",""\n', encoding="utf-8")

    assert (
        main(
            [
                str(backup_root),
                "--db-dir",
                "db1",
                "--csv",
                str(first),
                "--csv",
                str(second),
            ]
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "must be inside" in err
    assert not (db1 / "manifest.sqlite3.migrating").exists()
    assert not (db1 / "manifest.sqlite3").exists()


def test_main_rejects_explicit_csv_outside_db_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "db").mkdir()
    outside = tmp_path / "outside.csv"
    outside.write_text('"d","x",""\n', encoding="utf-8")
    assert main([str(tmp_path), "--csv", str(outside)]) == 1
    err = capsys.readouterr().err
    assert "inside" in err


def test_main_rejects_explicit_csv_non_csv_suffix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "data").mkdir()
    db = tmp_path / "db"
    db.mkdir()
    wrong = db / "version.txt"
    wrong.write_text('"d","x",""\n', encoding="utf-8")
    assert main([str(tmp_path), "--csv", str(wrong)]) == 1
    err = capsys.readouterr().err
    assert "must end with .csv" in err


def test_main_rejects_explicit_csv_uppercase_suffix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "data").mkdir()
    db = tmp_path / "db"
    db.mkdir()
    wrong = db / "version.CSV"
    wrong.write_text('"d","x",""\n', encoding="utf-8")
    assert main([str(tmp_path), "--csv", str(wrong)]) == 1
    err = capsys.readouterr().err
    assert "must end with .csv" in err


def test_main_rejects_duplicate_explicit_csv_basenames(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "backup"
    db = root / "db"
    db.mkdir(parents=True)
    (root / "data").mkdir()
    same = db / "same.csv"
    same.write_text('"d","x",""\n', encoding="utf-8")
    duplicate_ref = db / "child" / ".." / "same.csv"
    assert main([str(root), "--csv", str(same), "--csv", str(duplicate_ref)]) == 1
    err = capsys.readouterr().err
    assert "duplicate --csv basenames" in err


def test_main_apply_requires_existing_data_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "db"
    db.mkdir()
    (db / "v.csv").write_text('"d","x",""\n', encoding="utf-8")
    assert main([str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "data directory does not exist" in err


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


def test_created_at_infers_from_parsable_version_stem(tmp_path: Path) -> None:
    manifest = tmp_path / "2026-02-01T094441.csv"
    manifest.write_text('"d","x",""\n', encoding="utf-8")
    inferred = infer_created_at_for_manifests([manifest])
    assert len(inferred) == 1
    assert inferred[0].version_name == "2026-02-01T094441"

    ts = time.mktime(datetime(2026, 2, 1, 9, 44, 41).timetuple())
    expected = float(round(ts * 1000)) / 1000.0
    assert inferred[0].created_at == expected


def test_created_at_falls_back_to_manifest_mtime_for_non_parsable_stem(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "release-v2.csv"
    manifest.write_text('"d","x",""\n', encoding="utf-8")
    mtime = 1_712_500_000.123
    os.utime(manifest, (mtime, mtime))

    inferred = infer_created_at_for_manifests([manifest])
    assert len(inferred) == 1
    assert inferred[0].version_name == "release-v2"
    assert inferred[0].created_at == float(round(mtime * 1000)) / 1000.0


def test_created_at_logs_collision_and_uses_lexicographic_tie_break(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    z_manifest = tmp_path / "zzz.csv"
    a_manifest = tmp_path / "aaa.csv"
    z_manifest.write_text('"d","x",""\n', encoding="utf-8")
    a_manifest.write_text('"d","x",""\n', encoding="utf-8")
    shared_mtime = 1_712_500_000.0
    os.utime(z_manifest, (shared_mtime, shared_mtime))
    os.utime(a_manifest, (shared_mtime, shared_mtime))

    with caplog.at_level("WARNING"):
        inferred = infer_created_at_for_manifests([z_manifest, a_manifest])

    assert [item.version_name for item in inferred] == ["aaa", "zzz"]
    assert inferred[0].created_at == inferred[1].created_at
    assert "created_at collision" in caplog.text
    assert "lexicographic" in caplog.text


def test_created_at_ignores_dot_prefixed_manifests(tmp_path: Path) -> None:
    regular = tmp_path / "v1.csv"
    dotprefixed = tmp_path / ".pending__v2.csv"
    regular.write_text('"d","x",""\n', encoding="utf-8")
    dotprefixed.write_text('"d","x",""\n', encoding="utf-8")

    inferred = infer_created_at_for_manifests([regular, dotprefixed])
    assert [item.version_name for item in inferred] == ["v1"]
