"""CHECK-command behavior tests for implementation `run_check`."""

from __future__ import annotations

from pathlib import Path

import pytest

from backuper.implementation.cli import run_check
import backuper.legacy.implementation.backup as legacy_backup
from backuper.legacy.implementation.commands import CheckCommand, NewCommand
from backuper.legacy.implementation.csv_db import CsvDb as LegacyCsvDb
from backuper.legacy.implementation.config import CsvDbConfig as LegacyCsvDbConfig


def _seed_backup(destination: Path, source: Path, *, version: str = "v1") -> None:
    source.mkdir()
    (source / "file.txt").write_text("payload", encoding="utf-8")
    legacy_backup.new(NewCommand(version=version, source=str(source), location=str(destination)))


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

    with pytest.raises(ValueError, match="Backup version named unknown does not exists"):
        run_check(cmd)

    with pytest.raises(ValueError, match="Backup version named unknown does not exists"):
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
