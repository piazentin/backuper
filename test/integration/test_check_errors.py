"""CHECK-command behavior tests for implementation `run_check`."""

from __future__ import annotations

from pathlib import Path

import pytest
from backuper.commands import CheckCommand, NewCommand, UpdateCommand
from backuper.components.csv_db import CsvDb
from backuper.config import CsvDbConfig
from backuper.entrypoints.cli import run_check, run_new, run_update


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


def test_run_check_raises_when_location_missing(tmp_path: Path) -> None:
    missing_backup = tmp_path / "missing"
    cmd = CheckCommand(location=str(missing_backup))

    with pytest.raises(ValueError, match="destination path .* does not exists"):
        run_check(cmd)


def test_run_check_raises_when_version_missing(tmp_path: Path) -> None:
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    _seed_backup(backup, source, version="v1")
    cmd = CheckCommand(location=str(backup), version="unknown")

    with pytest.raises(
        ValueError, match="Backup version named unknown does not exists"
    ):
        run_check(cmd)


def test_run_check_prints_no_errors_for_valid_backup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    _seed_backup(backup, source, version="v1")

    errors = run_check(CheckCommand(location=str(backup)))
    captured = capsys.readouterr()

    assert errors == []
    assert "No errors found!" in captured.out


def test_run_check_reports_manifest_mismatch_when_csv_metadata_wrong_but_blob_exists(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Wrong stored_location / is_compressed in CSV while blob exists confuses restore."""
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    source.mkdir()
    (source / "big.txt").write_text("x" * 2048, encoding="utf-8")
    run_new(NewCommand(version="v1", source=str(source), location=str(backup)))

    db = CsvDb(CsvDbConfig(backup_dir=str(backup)))
    version = db.get_version_by_name("v1")
    stored_file = db.get_files_for_version(version)[0]
    assert stored_file.is_compressed
    assert stored_file.stored_location.endswith(".zip")

    db_cfg = CsvDbConfig(backup_dir=str(backup))
    csv_path = backup / db_cfg.backup_db_dir / f"v1{db_cfg.csv_file_extension}"
    text = csv_path.read_text(encoding="utf-8")
    bad_loc = stored_file.stored_location.removesuffix(".zip")
    text = text.replace(
        f'"{stored_file.stored_location}"',
        f'"{bad_loc}"',
        1,
    )
    text = text.replace(',"True",', ',"False",', 1)
    csv_path.write_text(text, encoding="utf-8")

    capsys.readouterr()
    errors = run_check(CheckCommand(location=str(backup), version="v1"))
    out = capsys.readouterr().out
    assert len(errors) == 1
    assert "Manifest metadata mismatch" in errors[0]
    assert stored_file.restore_path in errors[0]
    assert errors[0] in out
    assert "No errors found!" not in out


def test_run_check_reports_missing_blobs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    _seed_backup(backup, source, version="v1")

    db = CsvDb(CsvDbConfig(backup_dir=str(backup)))
    version = db.get_version_by_name("v1")
    stored_file = db.get_files_for_version(version)[0]
    stored_blob = backup / "data" / stored_file.stored_location
    stored_blob.unlink()
    capsys.readouterr()

    check_command = CheckCommand(location=str(backup), version="v1")
    errors = run_check(check_command)
    stdout = capsys.readouterr().out

    assert len(errors) == 1
    assert errors[0].startswith("Missing hash ")
    assert stored_file.restore_path in errors[0]
    assert " in v1" in errors[0]
    assert errors[0] in stdout


def test_run_check_all_versions_aggregates_missing_blobs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "backup"
    source_v1 = tmp_path / "src_v1"
    source_v2 = tmp_path / "src_v2"
    _seed_backup(backup, source_v1, version="v1")
    _seed_backup_version(backup, source_v2, version="v2")

    db = CsvDb(CsvDbConfig(backup_dir=str(backup)))
    for version_name in ("v1", "v2"):
        version = db.get_version_by_name(version_name)
        stored_file = db.get_files_for_version(version)[0]
        stored_blob = backup / "data" / stored_file.stored_location
        stored_blob.unlink()
    capsys.readouterr()

    check_command = CheckCommand(location=str(backup))
    implementation_errors = run_check(check_command)
    implementation_stdout = capsys.readouterr().out

    assert len(implementation_errors) == 2
    assert " in v1" in implementation_stdout
    assert " in v2" in implementation_stdout
    assert all(error.startswith("Missing hash ") for error in implementation_errors)
