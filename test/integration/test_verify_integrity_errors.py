"""VERIFY-INTEGRITY command behavior tests for `run_verify_integrity`."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from backuper.commands import NewCommand, UpdateCommand, VerifyIntegrityCommand
from backuper.config import SqliteDbConfig
from backuper.entrypoints.cli import run_new, run_update, run_verify_integrity
from backuper.models import CliUsageError, VersionNotFoundError


def _manifest_sqlite(backup: Path) -> Path:
    cfg = SqliteDbConfig(backup_dir=str(backup))
    return backup / cfg.backup_db_dir / cfg.sqlite_filename


def _first_file_row(backup: Path, version: str) -> sqlite3.Row:
    path = _manifest_sqlite(backup)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT restore_path, storage_location, compression
            FROM version_files
            WHERE version_name = ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (version,),
        ).fetchone()
    assert row is not None
    return row


def _seed_backup(destination: Path, source: Path, *, version: str = "v1") -> None:
    source.mkdir()
    (source / "file.txt").write_text("payload", encoding="utf-8")
    run_new(NewCommand(version=version, source=str(source), location=str(destination)))


def _seed_backup_version(destination: Path, source: Path, *, version: str) -> None:
    source.mkdir()
    (source / "file.txt").write_text(f"payload-{version}", encoding="utf-8")
    run_update(
        UpdateCommand(version=version, source=str(source), location=str(destination))
    )


def test_run_verify_integrity_raises_when_location_missing(tmp_path: Path) -> None:
    missing_backup = tmp_path / "missing"
    cmd = VerifyIntegrityCommand(location=str(missing_backup))

    with pytest.raises(CliUsageError, match="destination path .* does not exist"):
        run_verify_integrity(cmd)


def test_run_verify_integrity_raises_when_version_missing(tmp_path: Path) -> None:
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    _seed_backup(backup, source, version="v1")
    cmd = VerifyIntegrityCommand(location=str(backup), version="unknown")

    with pytest.raises(
        VersionNotFoundError, match="Backup version named unknown does not exist"
    ):
        run_verify_integrity(cmd)


def test_run_verify_integrity_prints_no_errors_for_valid_backup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    _seed_backup(backup, source, version="v1")

    errors = run_verify_integrity(VerifyIntegrityCommand(location=str(backup)))
    captured = capsys.readouterr()

    assert errors == []
    assert "No errors found!" in captured.out


def test_run_verify_integrity_json_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    _seed_backup(backup, source, version="v1")
    capsys.readouterr()

    errors = run_verify_integrity(
        VerifyIntegrityCommand(location=str(backup), json_output=True)
    )
    captured = capsys.readouterr()

    assert errors == []
    assert json.loads(captured.out) == {"errors": []}
    assert "No errors found!" not in captured.out


def test_run_verify_integrity_json_with_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    _seed_backup(backup, source, version="v1")

    row = _first_file_row(backup, "v1")
    stored_blob = backup / "data" / row["storage_location"]
    stored_blob.unlink()
    capsys.readouterr()

    errors = run_verify_integrity(
        VerifyIntegrityCommand(location=str(backup), version="v1", json_output=True),
    )
    captured = capsys.readouterr()

    assert len(errors) == 1
    assert json.loads(captured.out) == {"errors": errors}


def test_run_verify_integrity_reports_manifest_mismatch_when_metadata_wrong_but_blob_exists(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Wrong storage_location / compression in manifest while blob exists."""
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    source.mkdir()
    (source / "big.txt").write_text("x" * 2048, encoding="utf-8")
    run_new(NewCommand(version="v1", source=str(source), location=str(backup)))

    row = _first_file_row(backup, "v1")
    stored_location = str(row["storage_location"])
    restore_path = str(row["restore_path"])
    assert str(row["compression"]) == "zip"
    assert stored_location.endswith(".zip")

    bad_loc = stored_location.removesuffix(".zip")
    db_path = _manifest_sqlite(backup)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE version_files
            SET storage_location = ?, compression = 'none'
            WHERE version_name = ? AND restore_path = ?
            """,
            (bad_loc, "v1", restore_path),
        )
        conn.commit()

    capsys.readouterr()
    errors = run_verify_integrity(
        VerifyIntegrityCommand(location=str(backup), version="v1")
    )
    out = capsys.readouterr().out
    assert len(errors) == 1
    assert "Manifest metadata mismatch" in errors[0]
    assert restore_path in errors[0]
    assert errors[0] in out
    assert "No errors found!" not in out


def test_run_verify_integrity_reports_missing_blobs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    _seed_backup(backup, source, version="v1")

    row = _first_file_row(backup, "v1")
    restore_path = Path(str(row["restore_path"]))
    stored_blob = backup / "data" / row["storage_location"]
    stored_blob.unlink()
    capsys.readouterr()

    verify_integrity_command = VerifyIntegrityCommand(
        location=str(backup), version="v1"
    )
    errors = run_verify_integrity(verify_integrity_command)
    stdout = capsys.readouterr().out

    assert len(errors) == 1
    assert errors[0].startswith("Missing hash ")
    assert str(restore_path) in errors[0]
    assert " in v1" in errors[0]
    assert errors[0] in stdout


def test_run_verify_integrity_all_versions_aggregates_missing_blobs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "backup"
    source_v1 = tmp_path / "src_v1"
    source_v2 = tmp_path / "src_v2"
    _seed_backup(backup, source_v1, version="v1")
    _seed_backup_version(backup, source_v2, version="v2")

    for version_name in ("v1", "v2"):
        row = _first_file_row(backup, version_name)
        stored_blob = backup / "data" / row["storage_location"]
        stored_blob.unlink()
    capsys.readouterr()

    verify_integrity_command = VerifyIntegrityCommand(location=str(backup))
    implementation_errors = run_verify_integrity(verify_integrity_command)
    implementation_stdout = capsys.readouterr().out

    assert len(implementation_errors) == 2
    assert " in v1" in implementation_stdout
    assert " in v2" in implementation_stdout
    assert all(error.startswith("Missing hash ") for error in implementation_errors)
