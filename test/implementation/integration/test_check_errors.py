"""CHECK-command behavior tests for implementation `run_check`."""

from __future__ import annotations

from pathlib import Path

import backuper.legacy.implementation.backup as legacy_backup
import pytest
from backuper.implementation.entrypoints.cli import run_check
from backuper.legacy.implementation.commands import (
    CheckCommand,
    NewCommand,
    UpdateCommand,
)
from backuper.legacy.implementation.config import CsvDbConfig as LegacyCsvDbConfig
from backuper.legacy.implementation.csv_db import CsvDb as LegacyCsvDb


def _seed_backup(destination: Path, source: Path, *, version: str = "v1") -> None:
    source.mkdir()
    (source / "file.txt").write_text("payload", encoding="utf-8")
    legacy_backup.new(
        NewCommand(version=version, source=str(source), location=str(destination))
    )


def _seed_backup_version(destination: Path, source: Path, *, version: str) -> None:
    source.mkdir()
    (source / "file.txt").write_text(f"payload-{version}", encoding="utf-8")
    legacy_backup.update(
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

    with pytest.raises(
        ValueError, match="Backup version named unknown does not exists"
    ):
        legacy_backup.check(cmd)


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


def test_run_check_reports_missing_blobs_with_legacy_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    _seed_backup(backup, source, version="v1")

    legacy_db = LegacyCsvDb(LegacyCsvDbConfig(backup_dir=str(backup)))
    version = legacy_db.get_version_by_name("v1")
    stored_file = legacy_db.get_files_for_version(version)[0]
    stored_blob = backup / "data" / stored_file.stored_location
    stored_blob.unlink()
    capsys.readouterr()

    check_command = CheckCommand(location=str(backup), version="v1")
    implementation_errors = run_check(check_command)
    implementation_stdout = capsys.readouterr().out

    legacy_errors = legacy_backup.check(check_command)
    legacy_stdout = capsys.readouterr().out

    assert implementation_errors == legacy_errors
    assert implementation_stdout == legacy_stdout
    assert implementation_errors[0].startswith("Missing hash ")


def test_run_check_all_versions_aggregates_missing_blobs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "backup"
    source_v1 = tmp_path / "src_v1"
    source_v2 = tmp_path / "src_v2"
    _seed_backup(backup, source_v1, version="v1")
    _seed_backup_version(backup, source_v2, version="v2")

    legacy_db = LegacyCsvDb(LegacyCsvDbConfig(backup_dir=str(backup)))
    for version_name in ("v1", "v2"):
        version = legacy_db.get_version_by_name(version_name)
        stored_file = legacy_db.get_files_for_version(version)[0]
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
