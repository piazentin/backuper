"""RESTORE-command tests for implementation `run_restore`."""

from __future__ import annotations

import filecmp
from pathlib import Path

import backuper.legacy.implementation.backup as legacy_backup
import pytest
from backuper.implementation.commands import RestoreCommand
from backuper.implementation.entrypoints.cli import run_restore
from backuper.legacy.implementation.commands import (
    NewCommand,
    UpdateCommand,
)
from backuper.legacy.implementation.commands import (
    RestoreCommand as LegacyRestoreCommand,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _seed_backup(destination: Path, source: Path, *, version: str = "v1") -> None:
    source.mkdir()
    (source / "file.txt").write_text("payload", encoding="utf-8")
    legacy_backup.new(
        NewCommand(version=version, source=str(source), location=str(destination))
    )


def test_run_restore_raises_when_backup_root_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    dest = tmp_path / "dest"
    cmd = RestoreCommand(
        location=str(missing),
        destination=str(dest),
        version_name="v1",
    )

    with pytest.raises(ValueError, match="Backup source path .* does not exist"):
        run_restore(cmd)


def test_run_restore_raises_when_destination_not_empty(tmp_path: Path) -> None:
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    dest = tmp_path / "dest"
    _seed_backup(backup, source, version="v1")
    dest.mkdir()
    (dest / "existing.txt").write_text("block", encoding="utf-8")

    cmd = RestoreCommand(
        location=str(backup),
        destination=str(dest),
        version_name="v1",
    )
    with pytest.raises(ValueError, match="already exists and is not empty"):
        run_restore(cmd)


def test_run_restore_raises_when_version_missing(tmp_path: Path) -> None:
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    dest = tmp_path / "dest"
    _seed_backup(backup, source, version="v1")
    cmd = RestoreCommand(
        location=str(backup),
        destination=str(dest),
        version_name="unknown",
    )

    with pytest.raises(
        ValueError, match="Backup version unknown does not exist in source"
    ):
        run_restore(cmd)

    with pytest.raises(
        ValueError, match="Backup version unknown does not exists in source"
    ):
        legacy_backup.restore(
            LegacyRestoreCommand(
                location=str(backup),
                destination=str(dest),
                version_name="unknown",
            )
        )


def test_run_restore_restores_fixture_tree(tmp_path: Path) -> None:
    fixture_source = _repo_root() / "test" / "resources" / "bkp_test_sources_new"
    backup = tmp_path / "backup"
    dest = tmp_path / "restored"
    legacy_backup.new(
        NewCommand(version="test", source=str(fixture_source), location=str(backup))
    )

    run_restore(
        RestoreCommand(
            location=str(backup),
            destination=str(dest),
            version_name="test",
        )
    )

    comp = filecmp.dircmp(str(fixture_source), str(dest))
    assert sorted(comp.common_files) == [
        "LICENSE",
        "text_file1 copy.txt",
        "text_file1.txt",
    ]
    assert sorted(comp.subdirs["subdir"].common_files) == ["starry_night.png"]
    assert sorted(comp.subdirs["subdir"].common_dirs) == ["empty dir"]


def test_run_restore_prints_restoring_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    dest = tmp_path / "out"
    _seed_backup(backup, source, version="v1")
    capsys.readouterr()

    run_restore(
        RestoreCommand(
            location=str(backup),
            destination=str(dest),
            version_name="v1",
        )
    )
    out = capsys.readouterr().out
    assert "Restoring " in out
    assert str(dest) in out


def test_run_restore_allows_empty_existing_destination(tmp_path: Path) -> None:
    backup = tmp_path / "backup"
    source = tmp_path / "src"
    dest = tmp_path / "dest"
    _seed_backup(backup, source, version="v1")
    dest.mkdir()
    assert not any(dest.iterdir())

    run_restore(
        RestoreCommand(
            location=str(backup),
            destination=str(dest),
            version_name="v1",
        )
    )
    assert (dest / "file.txt").read_text(encoding="utf-8") == "payload"


def test_run_restore_second_version_after_update(tmp_path: Path) -> None:
    backup = tmp_path / "backup"
    source_v1 = tmp_path / "src_v1"
    source_v2 = tmp_path / "src_v2"
    dest = tmp_path / "out"
    _seed_backup(backup, source_v1, version="v1")
    source_v2.mkdir()
    (source_v2 / "file.txt").write_text("v2-payload", encoding="utf-8")
    legacy_backup.update(
        UpdateCommand(version="v2", source=str(source_v2), location=str(backup))
    )

    run_restore(
        RestoreCommand(
            location=str(backup),
            destination=str(dest),
            version_name="v2",
        )
    )
    assert (dest / "file.txt").read_text(encoding="utf-8") == "v2-payload"
