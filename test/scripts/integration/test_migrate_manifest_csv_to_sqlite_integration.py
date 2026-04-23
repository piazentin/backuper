"""Integration tests for ``scripts.migrate_manifest_csv_to_sqlite``."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from scripts.migrate_manifest_csv_to_sqlite.__main__ import (
    _CSV_ARCHIVE_DIRNAME,
    _LIVE_SQLITE_FILENAME,
    main,
)


def _write_minimal_canonical_manifest(path: Path, *, name: str) -> None:
    path.write_text(
        (
            f'"f","{name}.txt","abc","aa/bb/abc.zip","False","3","1.0"\n'
            f'"d","{name}/",""\n'
        ),
        encoding="utf-8",
    )


@pytest.fixture
def backup_root(tmp_path: Path) -> Path:
    root = tmp_path / "backup"
    (root / "db").mkdir(parents=True)
    (root / "data").mkdir()
    return root


def test_apply_archives_csvs_after_publish_and_checkpoints_wal(
    backup_root: Path,
) -> None:
    db = backup_root / "db"
    first_manifest = db / "v1.csv"
    second_manifest = db / "v2.csv"
    _write_minimal_canonical_manifest(first_manifest, name="first")
    _write_minimal_canonical_manifest(second_manifest, name="second")

    assert main([str(backup_root)]) == 0

    live_db = db / _LIVE_SQLITE_FILENAME
    assert live_db.exists()

    archive_root = db / _CSV_ARCHIVE_DIRNAME
    run_dirs = [entry for entry in archive_root.iterdir() if entry.is_dir()]
    assert len(run_dirs) == 1
    archived_names = sorted(path.name for path in run_dirs[0].iterdir())
    assert archived_names == ["v1.csv", "v2.csv"]
    assert not first_manifest.exists()
    assert not second_manifest.exists()

    wal_path = Path(f"{live_db}-wal")
    assert not wal_path.exists() or wal_path.stat().st_size == 0

    with sqlite3.connect(live_db) as conn:
        versions = conn.execute(
            "SELECT name, state FROM versions ORDER BY name ASC"
        ).fetchall()
    assert versions == [("v1", "completed"), ("v2", "completed")]


def test_second_apply_exits_cleanly_when_no_csv_manifests_remain(
    backup_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = backup_root / "db"
    manifest = db / "v.csv"
    _write_minimal_canonical_manifest(manifest, name="only")

    assert main([str(backup_root)]) == 0
    assert main([str(backup_root)]) == 0

    err = capsys.readouterr().err
    assert "No CSV manifest files found" in err
