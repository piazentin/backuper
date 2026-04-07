"""UPDATE precondition errors for `run_update`."""

from __future__ import annotations

from pathlib import Path

import pytest
from backuper.commands import NewCommand, UpdateCommand
from backuper.entrypoints.cli import run_new, run_update
from backuper.models import CliUsageError, VersionAlreadyExistsError


def test_run_update_raises_when_source_missing(tmp_path: Path) -> None:
    backup = tmp_path / "backup"
    backup.mkdir()
    missing_src = tmp_path / "nope"
    cmd = UpdateCommand(version="v2", source=str(missing_src), location=str(backup))

    with pytest.raises(CliUsageError, match="source path .* does not exist"):
        run_update(cmd)


def test_run_update_raises_when_destination_missing(tmp_path: Path) -> None:
    """`run_update` requires an existing backup root before opening the DB."""
    src = tmp_path / "src"
    src.mkdir()
    missing_dst = tmp_path / "no_backup"
    cmd = UpdateCommand(version="v2", source=str(src), location=str(missing_dst))

    with pytest.raises(CliUsageError, match="destination path .* does not exist"):
        run_update(cmd)


def test_run_update_raises_when_version_already_in_database(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "f.txt").write_text("x", encoding="utf-8")
    backup = tmp_path / "backup"
    version = "same_version"

    run_new(NewCommand(version, str(src), str(backup)))
    cmd = UpdateCommand(version=version, source=str(src), location=str(backup))

    with pytest.raises(
        VersionAlreadyExistsError, match="already a backup versioned with the name"
    ):
        run_update(cmd)
